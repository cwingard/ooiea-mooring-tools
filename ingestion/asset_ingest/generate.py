"""Generate a deployment's D and R ingestion CSVs from the site templates.

Inputs
------
* templates/<SITE>_D_ingest.csv and <SITE>_R_ingest.csv: every stream row
  the site uses, with '{deployment}' where the D000NN/R000NN directory goes
  and '{dcl}' where an instrument's logger number goes. Engineering rows
  (port 00) carry their logger literally.
* the deployment configuration workbook: site, deployment number, and the
  DCL each instrument is plugged into.
* asset_management deployment/<SITE>_Deploy.csv: which reference
  designators were deployed (run the deploy tool first).

Rules
-----
* A reference designator not deployed in asset_management is written
  commented out with status 'Not Deployed'.
* An instrument recorded by a CTDBP (same node and port in the reference
  designator, e.g. MFD37-03-DOSTAD000 on MFD37-03-CTDBPC000) takes the
  CTDBP's DCL; its own DCL:Port row, if any, is not used, and a
  disagreeing value is listed for information.
* Any other row is written exactly as the template has it (active or
  commented, status, notes), with the tokens filled in.
* The run stops, writing nothing, when a template reference designator is
  not in asset_management's deployment, when a deployed instrument has no
  DCL:Port entry, or when its DCL is not one of the sheet's loggers.
* Listed for information, not errors: deployed reference designators with
  no template row (e.g. METBK sub-sensors, which have no stream of their
  own; a new instrument missing from the templates also shows up here), and
  sheet instruments without a reference designator (one-offs).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from asset_ingest.config_wiring import ConfigWiring, read_config_wiring
from asset_ingest.deploy_state import read_deploy_state
from asset_ingest.ingest_file import IngestRow, ctd_host, read_ingest_csv

KINDS = ('D', 'R')


class GenerateError(ValueError):
    """The inputs are inconsistent; nothing was written."""


@dataclass
class Generated:
    site: str
    dep_num: int
    files: dict[str, list[IngestRow]]           # file name -> rows
    not_deployed: list[str] = field(default_factory=list)
    no_stream: list[str] = field(default_factory=list)
    ignored_config: list[str] = field(default_factory=list)
    follows_ctd: list[str] = field(default_factory=list)


def template_path(templates: str | Path, site: str, kind: str) -> Path:
    return Path(templates) / f'{site}_{kind}_ingest.csv'


def output_name(site: str, kind: str, dep_num: int) -> str:
    return f'{site}_{kind}{dep_num:05d}_ingest.csv'


def _resolve_dcl(refdes: str, deployed: bool, wiring: ConfigWiring, errors: list[str]) -> int:
    entry = wiring.find(refdes)
    if entry is not None:
        entry.used = True
    if entry is None or entry.dcl is None:
        if deployed:
            errors.append(f'{refdes}: deployed per asset_management but has no DCL:Port value in the config')
        # commented out as Not Deployed; fall back to the node's own number
        return int(refdes[12:14])
    if deployed and wiring.loggers and entry.dcl not in wiring.loggers:
        errors.append(f'{refdes}: config row {entry.row} puts it on DCL{entry.dcl:02d}, '
                      f'which is not in the Platform Control rows')
    return entry.dcl


def generate(config: str | Path, asset_management: str | Path, templates: str | Path) -> Generated:
    """Build the D and R ingestion rows for the deployment in `config`.

    Parameters
    ----------
    config : str or Path
        Deployment configuration workbook.
    asset_management : str or Path
        Root of the asset-management repo.
    templates : str or Path
        Folder holding <SITE>_D_ingest.csv and <SITE>_R_ingest.csv.

    Returns
    -------
    Generated

    Raises
    ------
    GenerateError
        With every problem found, one per line.
    """
    wiring = read_config_wiring(config)
    site, dep_num = wiring.site, wiring.dep_num

    all_state = read_deploy_state(asset_management, site)
    if dep_num not in all_state:
        raise GenerateError(f'{site}_Deploy.csv has no deployment {dep_num}; run the deploy tool first')
    state = all_state[dep_num]

    template_rows: dict[str, list[IngestRow]] = {}
    for kind in KINDS:
        path = template_path(templates, site, kind)
        if not path.exists():
            raise GenerateError(f'No template {path}')
        template_rows[kind] = read_ingest_csv(path)[1]

    errors: list[str] = []
    template_refdes = {r.reference_designator for rows in template_rows.values() for r in rows}
    for refdes in sorted(template_refdes - set(state)):
        errors.append(f'{refdes}: in the templates but not in {site}_Deploy.csv deployment {dep_num}')

    dcl_cache: dict[str, int] = {}
    follows_ctd: list[str] = []
    files: dict[str, list[IngestRow]] = {}
    for kind in KINDS:
        deployment = f'{kind}{dep_num:05d}'
        out: list[IngestRow] = []
        for row in template_rows[kind]:
            refdes = row.reference_designator
            deployed = state.get(refdes, False)
            mask = row.filename_mask.replace('{deployment}', deployment)
            if '{dcl}' in mask:
                if refdes not in dcl_cache:
                    host = ctd_host(refdes, template_refdes)
                    if host is None:
                        dcl_cache[refdes] = _resolve_dcl(refdes, deployed, wiring, errors)
                    else:
                        if deployed and not state.get(host, False):
                            errors.append(f'{refdes}: deployed per asset_management but its CTDBP {host} is not')
                        if host not in dcl_cache:
                            dcl_cache[host] = _resolve_dcl(host, state.get(host, False), wiring, errors)
                        dcl_cache[refdes] = dcl_cache[host]
                        own = wiring.find(refdes)
                        if own is not None:
                            own.used = True
                        if own is not None and own.dcl is not None and own.dcl != dcl_cache[host]:
                            follows_ctd.append(f'{refdes}: config row {own.row} says DCL{own.dcl:02d}, '
                                               f'using DCL{dcl_cache[host]:02d} from {host}')
                mask = mask.replace('{dcl}', f'{dcl_cache[refdes]:02d}')
            if '{' in mask:
                errors.append(f'{refdes}: unknown token left in template mask {mask!r}')
            new = row.with_(filename_mask=mask, line=0)
            if not deployed:
                new = new.with_(active=False, status='Not Deployed', notes='')
            out.append(new)
        files[output_name(site, kind, dep_num)] = out

    if errors:
        raise GenerateError('\n'.join(errors))

    return Generated(
        site=site,
        dep_num=dep_num,
        files=files,
        not_deployed=sorted(r for r, d in state.items() if not d),
        no_stream=sorted(r for r, d in state.items() if d and r not in template_refdes),
        ignored_config=[f'{e.cls} ({e.section}, row {e.row})' for e in wiring.entries if not e.used],
        follows_ctd=follows_ctd,
    )
