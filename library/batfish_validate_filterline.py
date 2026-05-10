#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: batfish_validate_filterline

short_description: Valide la reachability des lignes de filters/policies via filterLineReachability().

version_added: "1.0.0"

description: >
  Utilise la question Batfish filterLineReachability() pour vérifier que certaines
  ACL/policies n'ont pas de lignes "mortes" (unreachable) ou, au contraire, que
  l'on s'attend bien à ce qu'elles soient inatteignables.

  Ce module ne teste PAS un flux {src,dst,ports} précis (ça c'est searchFilters()
  et reachability()), mais la capacité générale d'une ligne à matcher un trafic quelconque.

options:
  host:
    description: Adresse du serveur Batfish (bf_session host).
    required: true
    type: str
  port:
    description: Port v2 HTTP du serveur Batfish.
    required: true
    type: int
  network:
    description: Nom logique du network Batfish (bf.set_network).
    required: true
    type: str
  snapshot:
    description: Nom du snapshot Batfish (bf.init_snapshot name=...).
    required: true
    type: str
  snapshot_dir:
    description: Chemin local du dossier snapshot (contenant configs/).
    required: true
    type: str

  flows:
    description: >
      Liste de tests sur des filters/policies.

      Pour chaque entrée, on vérifie si filterLineReachability() renvoie ou non
      des lignes inatteignables pour ce couple (node, filter_name).

      Exemple de test :

        - name: "Ligne FLUX_Test sur fortigat_ansible"
          node: "fortigat_ansible"            # NodeSpec côté Batfish
          filter_name: "zone~port4~to~zone~port2"  # FilterSpec côté Batfish
          match_criteria: "MATCH"             # "MATCH" = aucune ligne unreachable attendue
                                              # "UNREACHABLE" = on s'attend à au moins une ligne morte

      Les champs src/dst/ports éventuellement présents seront ignorés ici ; ils
      sont utiles pour d'autres modules (searchFilters/reachability).
    required: false
    type: list
    elements: dict
    default: []

author:
  - "Toi :)"
'''

EXAMPLES = r'''
- name: Vérifier que la policy FLUX_Test n'a pas de lignes mortes
  batfish_validate_filterline:
    host: 127.0.0.1
    port: 9996
    network: fortigate_lab
    snapshot: fortigate_snapshot_01
    snapshot_dir: /root/netops.fr/article/batfish/batfish/snapshot_fortigate
    flows:
      - name: "Ligne FLUX_Test sur fortigat_ansible"
        node: "fortigat_ansible"
        filter_name: "zone~port4~to~zone~port2"
        match_criteria: "MATCH"      # on attend 0 ligne unreachable
  register: bf_filterline

- name: Echouer si une ligne est unreachable
  fail:
    msg: "{{ bf_filterline.tests_summary }}"
  when: not bf_filterline.tests_ok
'''

RETURN = r'''
tests_ok:
  description: True si tous les tests sont conformes au critère (MATCH/UNREACHABLE).
  type: bool
  returned: always

tests_summary:
  description: Résumé global de la validation filterLineReachability().
  type: list
  elements: dict
  returned: always

details:
  description: >
    Liste détaillée, une entrée par test.

    Chaque entrée contient notamment :
      - name, node, filter_name, match_criteria
      - unreachable_count : nombre de lignes unreachable trouvées
      - unreachable_lines : liste des lignes unreachable (Sources, Unreachable_Line, ...)
      - ok, error
  type: list
  elements: dict
  returned: always

raw_batfish_errors:
  description: Erreurs brutes inattendues lors des appels Batfish.
  type: list
  elements: str
  returned: on failure
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from pybatfish.client.session import Session
    HAS_PYBATFISH = True
except Exception:
    HAS_PYBATFISH = False


def _serialize_filterline_df(df, max_rows=None):
    """
    Transforme le DataFrame filterLineReachability() en quelque chose
    de 100% sérialisable JSON (str, int, bool, list de str, ...).
    """
    if df is None or df.empty:
        return [], 0

    if max_rows is not None:
        df = df.head(max_rows)

    df = df.copy()

    for col in df.columns:
        def _convert_cell(v):
            # list/tuple/set -> liste de str
            if isinstance(v, (list, tuple, set)):
                return [str(x) for x in v]
            # types simples -> laissés tels quels
            if isinstance(v, (str, int, float, bool)) or v is None:
                return v
            # tout le reste -> str()
            return str(v)

        df[col] = df[col].apply(_convert_cell)

    records = df.to_dict(orient="records")
    return records, len(records)


def _interpret_match_criteria(raw_value):
    """
    MATCH / REACHABLE / OK => on attend 0 ligne unreachable
    UNREACHABLE / BLOCKED => on attend >= 1 ligne unreachable
    Autre / non défini     => par défaut on attend 0 ligne unreachable
    """
    if not raw_value:
        return False  # expect_unreachable = False

    v = str(raw_value).strip().upper()
    if v in ("UNREACHABLE", "BLOCKED"):
        return True
    # MATCH, REACHABLE, OK, etc.
    return False


def run_module():
    module_args = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', required=True),
        network=dict(type='str', required=True),
        snapshot=dict(type='str', required=True),
        snapshot_dir=dict(type='str', required=True),
        flows=dict(type='list', elements='dict', required=False, default=[]),
    )

    result = dict(
        changed=False,
        tests_ok=False,
        tests_summary=[],
        details=[],
        raw_batfish_errors=[],
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if not HAS_PYBATFISH:
        module.fail_json(msg="Le module Python pybatfish est requis (pip install pybatfish).", **result)

    if module.check_mode:
        result["tests_ok"] = True
        result["tests_summary"].append(dict(
            name="filterLineReachability()",
            ok=True,
            message="check_mode: tests non exécutés."
        ))
        module.exit_json(**result)

    host = module.params["host"]
    port = module.params["port"]
    network = module.params["network"]
    snapshot = module.params["snapshot"]
    snapshot_dir = module.params["snapshot_dir"]
    flows = module.params["flows"] or []

    try:
        bf = Session(host=host, port_v2=port, ssl=False)
        bf.set_network(network)
        bf.init_snapshot(snapshot_dir, name=snapshot, overwrite=True)
        bf.set_snapshot(snapshot)
    except Exception as e:
        result["raw_batfish_errors"].append(str(e))
        module.fail_json(msg=f"Erreur lors de l'initialisation Batfish: {e}", **result)

    # Pas de tests -> on considère OK et on sort
    if not flows:
        result["tests_ok"] = True
        result["details"] = []
        result["tests_summary"].append(dict(
            name="filterLineReachability()",
            ok=True,
            message="Aucun test filterLineReachability défini (ignoré).",
        ))
        module.exit_json(**result)

    all_ok = True
    details = []
    errors_global = []

    for flt in flows:
        name = flt.get("name") or f"{flt.get('node')} / {flt.get('filter_name') or flt.get('filter')}"
        node = flt.get("node")
        filter_name = flt.get("filter_name") or flt.get("filter")
        match_criteria = flt.get("match_criteria") or "MATCH"
        expect_unreachable = _interpret_match_criteria(match_criteria)

        entry = dict(
            name=name,
            node=node,
            filter_name=filter_name,
            match_criteria=match_criteria,
            unreachable_count=0,
            unreachable_lines=[],
            ok=False,
            error=None,
        )

        # Si on n'a ni node ni filter_name, ça n'a pas trop de sens
        if not node and not filter_name:
            entry["error"] = "config incomplète: 'node' ou 'filter_name' requis."
            entry["ok"] = False
            all_ok = False
            errors_global.append(f"{name}: {entry['error']}")
            details.append(entry)
            continue

        try:
            q_kwargs = {}
            if node:
                q_kwargs["nodes"] = node
            if filter_name:
                q_kwargs["filters"] = filter_name

            df = bf.q.filterLineReachability(**q_kwargs).answer().frame()
        except Exception as e:
            msg = f"Erreur filterLineReachability(): {e}"
            entry["error"] = msg
            entry["ok"] = False
            all_ok = False
            errors_global.append(f"{name}: {msg}")
            details.append(entry)
            continue

        records, count = _serialize_filterline_df(df)
        entry["unreachable_count"] = count
        entry["unreachable_lines"] = records

        if expect_unreachable:
            entry["ok"] = count > 0
            if not entry["ok"]:
                entry["error"] = "Aucune ligne unreachable trouvée alors qu'au moins une était attendue."
                all_ok = False
                errors_global.append(f"{name}: {entry['error']}")
        else:
            entry["ok"] = count == 0
            if not entry["ok"]:
                entry["error"] = f"{count} ligne(s) unreachable trouvée(s) alors qu'aucune n'était attendue."
                all_ok = False
                errors_global.append(f"{name}: {entry['error']}")

        details.append(entry)

    result["details"] = details
    result["tests_ok"] = all_ok

    if errors_global:
        msg = "Certains tests filterLineReachability sont en échec: " + "; ".join(errors_global)
    else:
        msg = f"Tous les tests filterLineReachability sont conformes ({len(details)})."

    result["tests_summary"].append(dict(
        name="filterLineReachability()",
        ok=all_ok,
        message=msg,
    ))

    module.exit_json(**result)


def main():
    run_module()


if __name__ == "__main__":
    main()

