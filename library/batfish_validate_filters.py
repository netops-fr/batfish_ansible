#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: batfish_validate_filters

short_description: Valide des flux au niveau des filters/policies via Batfish (searchFilters).

version_added: "1.0.0"

description: >
  Se connecte à un serveur Batfish, exécute la question searchFilters()
  pour une liste de flux, et vérifie que l'action observée (permit/deny)
  correspond à l'action attendue. Permet aussi de filtrer par nom de
  policy (motif) et/ou par nœud.

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
      Liste de flux à tester au niveau des filters/policies.
      Chaque entrée ressemble à :
        - name: "HTTP 10.0.10.1 -> 10.0.11.1:80 autorisé"
          src: "10.0.10.1"
          dst: "10.0.11.1"
          protocol: "tcp"
          src_port: 12345         # optionnel
          dst_port: 80            # optionnel
          expected_action: "permit"  # ou "deny"
          node: "fortigat_ansible"   # optionnel (specifier Batfish "nodes")
          filter: "FLUX_"           # motif à chercher dans Trace/Filter_Name (optionnel, * accepté)
    required: false
    type: list
    elements: dict
    default: []

author:
  - "Toi :)"
'''

EXAMPLES = r'''
- name: Vérifier qu'un flux HTTP est autorisé par les policies FLUX_
  batfish_validate_filters:
    host: 127.0.0.1
    port: 9996
    network: fortigate_lab
    snapshot: fortigate_snapshot_01
    snapshot_dir: /root/netops.fr/article/batfish/batfish/snapshot_fortigate
    flows:
      - name: "HTTP 10.0.10.1 -> 10.0.11.1:80 autorisé"
        src: "10.0.10.1"
        dst: "10.0.11.1"
        protocol: "tcp"
        dst_port: 80
        expected_action: "permit"
        filter: "FLUX_"
  register: bf_filters

- name: Echouer si un des tests de filters est KO
  fail:
    msg: "{{ bf_filters.tests_summary }}"
  when: not bf_filters.tests_ok
'''

RETURN = r'''
tests_ok:
  description: True si tous les tests de filters sont conformes, False sinon.
  type: bool
  returned: always

tests_summary:
  description: Liste de résumés (une entrée globale).
  type: list
  elements: dict
  returned: always

flows_details:
  description: >
    Détail par flux testé. Chaque entrée contient :
      - name, src, dst, protocol, src_port, dst_port, expected_action, node, filter_pattern
      - ok (bool)
      - error (string ou null)
      - actions_observed (liste des actions observées : PERMIT/DENY/...)
      - matches (liste des matches, avec Node, Filter_Name, Action, Trace, Flow)
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

# pybatfish imports
try:
    from pybatfish.client.session import Session
    from pybatfish.datamodel.flow import HeaderConstraints
    HAS_PYBATFISH = True
except Exception:
    HAS_PYBATFISH = False


def _normalize_protocol(proto: str) -> str:
    if not proto:
        return "tcp"
    return proto.lower()


def _df_to_records_str(df):
    """
    Convertit un DataFrame en liste de dict avec toutes les colonnes castées en str.
    """
    if df is None:
        return []
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def run_module():
    # Définition des arguments du module
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
        flows_details=[],
        raw_batfish_errors=[],
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if not HAS_PYBATFISH:
        module.fail_json(msg="Le module Python pybatfish est requis (pip install pybatfish).", **result)

    if module.check_mode:
        # Pas de changement, juste validation structure
        result['tests_ok'] = True
        result['tests_summary'].append(dict(
            name="Vérification des flux au niveau des filters (policies)",
            ok=True,
            message="check_mode: tests non exécutés."
        ))
        module.exit_json(**result)

    host = module.params['host']
    port = module.params['port']
    network = module.params['network']
    snapshot = module.params['snapshot']
    snapshot_dir = module.params['snapshot_dir']
    flows = module.params['flows'] or []

    try:
        # Ouverture de session Batfish
        bf = Session(host=host, port_v2=port, ssl=False)

        bf.set_network(network)
        bf.init_snapshot(snapshot_dir, name=snapshot, overwrite=True)
        bf.set_snapshot(snapshot)

        flows_details = []
        errors_global = []

        # Aucun flux → on considère OK mais on le dit clairement
        if not flows:
            result["tests_ok"] = True
            result["flows_details"] = []
            result["tests_summary"].append(dict(
                name="Vérification des flux au niveau des filters (policies)",
                ok=True,
                message="Aucun flux défini (tests ignorés)."
            ))
            module.exit_json(**result)

        for flt in flows:
            desc = flt.get("name") or f"{flt.get('src')} -> {flt.get('dst')}"
            src = flt.get("src")
            dst = flt.get("dst")
            proto = _normalize_protocol(flt.get("protocol") or "tcp")
            src_port = flt.get("src_port")
            dst_port = flt.get("dst_port")
            expected_action = (flt.get("expected_action") or "permit").lower()
            node = flt.get("node")  # peut être None
            filter_pattern = flt.get("filter")  # motif Python côté client uniquement

            entry = dict(
                name=str(desc),
                src=str(src) if src is not None else None,
                dst=str(dst) if dst is not None else None,
                protocol=proto,
                src_port=src_port,
                dst_port=dst_port,
                expected_action=expected_action,
                node=str(node) if node is not None else None,
                filter_pattern=str(filter_pattern) if filter_pattern is not None else None,
                ok=False,
                error=None,
                actions_observed=[],
                matches=[],
            )

            if not src or not dst:
                entry["error"] = "config incomplète (src/dst manquant)"
                flows_details.append(entry)
                errors_global.append(f"{desc}: {entry['error']}")
                continue

            # Construction HeaderConstraints
            headers_kwargs = {
                "srcIps": src,
                "dstIps": dst,
                "ipProtocols": [proto],
            }
            if src_port is not None:
                headers_kwargs["srcPorts"] = [int(src_port)]
            if dst_port is not None:
                headers_kwargs["dstPorts"] = [int(dst_port)]

            try:
                headers = HeaderConstraints(**headers_kwargs)

                q_kwargs = {
                    "headers": headers,
                    "action": expected_action,
                }
                if node:
                    q_kwargs["nodes"] = node

                df = bf.q.searchFilters(**q_kwargs).answer().frame()
            except Exception as e:
                msg = f"erreur searchFilters(): {e}"
                entry["error"] = msg
                flows_details.append(entry)
                errors_global.append(f"{desc}: {msg}")
                continue

            if df is None or df.empty:
                msg = "searchFilters() n'a retourné aucun résultat pour ces headers."
                entry["error"] = msg
                flows_details.append(entry)
                errors_global.append(f"{desc}: {msg}")
                continue

            # Normalisation en str
            df = df.copy()
            for col in ["Node", "Filter_Name", "Action", "Trace", "Flow"]:
                if col in df.columns:
                    df[col] = df[col].astype(str)

            # Filtre node côté Python (redondant mais sécurisant)
            if node and "Node" in df.columns:
                df = df[df["Node"] == node]

            # Filtrage motif filter_pattern côté Python
            if filter_pattern:
                raw_pattern = str(filter_pattern)
                substr = raw_pattern.replace("*", "")
                if substr:
                    mask = False
                    if "Trace" in df.columns:
                        mask = mask | df["Trace"].str.contains(substr, na=False)
                    if "Filter_Name" in df.columns:
                        mask = mask | df["Filter_Name"].str.contains(substr, na=False)
                    df = df[mask]

            if df.empty:
                msg = "Aucune ligne après filtrage node/policy/motif."
                entry["error"] = msg
                flows_details.append(entry)
                errors_global.append(f"{desc}: {msg}")
                continue

            # Extraction des matches (en str)
            cols = [c for c in ["Node", "Filter_Name", "Action", "Trace", "Flow"] if c in df.columns]
            matches = []
            for _, row in df[cols].iterrows():
                matches.append({
                    "Node": row.get("Node"),
                    "Filter_Name": row.get("Filter_Name"),
                    "Action": row.get("Action"),
                    "Trace": row.get("Trace"),
                    "Flow": row.get("Flow"),
                })
            entry["matches"] = matches

            if "Action" not in df.columns:
                msg = "colonne 'Action' absente du résultat searchFilters()."
                entry["error"] = msg
                flows_details.append(entry)
                errors_global.append(f"{desc}: {msg}")
                continue

            actions_observed = sorted(set(df["Action"]))
            entry["actions_observed"] = actions_observed

            if expected_action.upper() not in [a.upper() for a in actions_observed]:
                msg = (
                    f"action attendue '{expected_action}' NON trouvée "
                    f"(actions observées : {', '.join(actions_observed)})"
                )
                entry["error"] = msg
                flows_details.append(entry)
                errors_global.append(f"{desc}: {msg}")
                continue

            # Si on arrive ici: test OK
            entry["ok"] = True
            flows_details.append(entry)

        # Synthèse globale
        all_ok = all(e["ok"] for e in flows_details) if flows_details else True

        result["tests_ok"] = all_ok
        result["flows_details"] = flows_details

        if errors_global:
            msg = "Flux NON conformes aux filters selon Batfish: " + "; ".join(errors_global)
            result["tests_summary"].append(dict(
                name="Vérification des flux au niveau des filters (policies)",
                ok=False,
                message=msg,
            ))
        else:
            result["tests_summary"].append(dict(
                name="Vérification des flux au niveau des filters (policies)",
                ok=True,
                message=f"Tous les tests de filters sont conformes ({len(flows_details)})",
            ))

        module.exit_json(**result)

    except Exception as e:
        result["raw_batfish_errors"].append(str(e))
        module.fail_json(msg=f"Erreur lors de la validation Batfish (filters): {e}", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()

