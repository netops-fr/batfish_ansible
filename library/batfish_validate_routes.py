#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: batfish_validate_routes

short_description: Valide les routes et adjacences L3 vues par Batfish pour un snapshot donné.

version_added: "1.0.0"

description: >
  Se connecte à un serveur Batfish, récupère la table de routage (RIB)
  et la topologie L3, puis vérifie :
    - que certaines routes statiques attendues sont présentes,
    - (optionnel) l'absence de route par défaut 0.0.0.0/0,
    - la présence d'au moins une adjacency L3,
    - que certaines adjacences L3 attendues (interfaces + IP) sont présentes.

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

  expected_static_routes:
    description: >
      Liste de routes statiques attendues.
      Chaque entrée ressemble à :
        - node: "fortigat_ansible"
          network: "10.0.2.0/24"
          next_hop_ip: "10.0.0.2"   # optionnel, substring de Next_Hop
    required: false
    type: list
    elements: dict
    default: []

  check_no_default_route:
    description: >
      Si true, vérifie qu'aucune route 0.0.0.0/0 n'est présente
      dans la RIB globale.
    required: false
    type: bool
    default: true

  expected_l3_edges:
    description: >
      Liste d'adjacences L3 attendues.
      Chaque entrée ressemble à :
        - node: "fortigat_ansible"
          iface: "port2"
          ip: "10.0.0.1"
          remote_node: "forti02"
          remote_iface: "port2"
          remote_ip: "10.0.0.2"
    required: false
    type: list
    elements: dict
    default: []

author:
  - "Toi :)"
'''

EXAMPLES = r'''
- name: Vérifier routes statiques, absence de default route et adjacences L3
  batfish_validate_routes:
    host: 127.0.0.1
    port: 9996
    network: fortigate_lab
    snapshot: fortigate_snapshot_01
    snapshot_dir: /root/netops.fr/article/batfish/batfish/snapshot_fortigate
    expected_static_routes:
      - node: "fortigat_ansible"
        network: "10.0.2.0/24"
        next_hop_ip: "10.0.0.2"
      - node: "forti02"
        network: "10.0.1.0/24"
        next_hop_ip: "10.0.0.1"
    expected_l3_edges:
      - node: "fortigat_ansible"
        iface: "port2"
        ip: "10.0.0.1"
        remote_node: "forti02"
        remote_iface: "port2"
        remote_ip: "10.0.0.2"
      - node: "forti02"
        iface: "port2"
        ip: "10.0.0.2"
        remote_node: "fortigat_ansible"
        remote_iface: "port2"
        remote_ip: "10.0.0.1"
    check_no_default_route: true
  register: bf_routes

- name: Afficher la synthèse
  debug:
    var: bf_routes.tests_summary

- name: Echouer si les tests de routes/L3 sont KO
  fail:
    msg: "{{ bf_routes.tests_summary }}"
  when: not bf_routes.tests_ok
'''

RETURN = r'''
tests_ok:
  description: True si tous les tests de routes / topologie L3 sont conformes, False sinon.
  type: bool
  returned: always

tests_summary:
  description: >
    Liste de résumés par type de test :
      - "Routes statiques attendues présentes"
      - "Absence de route par défaut 0.0.0.0/0" (si check_no_default_route = true)
      - "Présence d'au moins une adjacency L3"
      - "Adjacences L3 attendues présentes (interfaces + IP)"
  type: list
  elements: dict
  returned: always

details:
  description: >
    Détail des tests :
      - expected_static_routes:
          ok: bool
          message: string
          missing: liste des routes manquantes (descriptions textuelles)
      - no_default_route (si check_no_default_route):
          ok: bool
          message: string
          found_defaults: liste de routes par défaut trouvées (Node/Network/Next_Hop)
      - l3_edges_presence:
          ok: bool
          message: string
          edges_count: nombre d'adjacences L3 vues
      - expected_l3_edges:
          ok: bool
          message: string
          missing: liste des adjacences manquantes (descriptions textuelles)
  type: dict
  returned: always

routes:
  description: Table de routage complète vue par Batfish (RIB) sérialisée.
  type: list
  elements: dict
  returned: always

l3_edges:
  description: Liste des adjacences L3 vues par Batfish (toutes les colonnes castées en string).
  type: list
  elements: dict
  returned: always

raw_batfish_errors:
  description: Liste brute d'erreurs exceptionnelles rencontrées.
  type: list
  elements: str
  returned: on failure
'''

from ansible.module_utils.basic import AnsibleModule

# pybatfish imports
try:
    from pybatfish.client.session import Session
    HAS_PYBATFISH = True
except Exception:
    HAS_PYBATFISH = False


def _df_to_records_str(df):
    """
    Sérialise un DataFrame en liste de dict, toutes colonnes castées en str
    (utile pour les objets pybatfish type Interface, Ip, NextHopInterface, etc.).
    """
    if df is None:
        return []
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def check_expected_static_routes(routes_df, expected_static_routes):
    """
    - Node + Network doivent matcher
    - Protocol doit être 'static'
    - si next_hop_ip renseigné, Next_Hop doit contenir cette IP
    Retourne (ok: bool, message: str, missing: [str]).
    """
    if not expected_static_routes:
        return True, "Aucune route attendue définie (test ignoré).", []

    if routes_df is None or routes_df.empty:
        return False, "Aucune route disponible dans Batfish.", [
            "Table de routage vide, impossible de valider les routes attendues."
        ]

    df = routes_df.copy()

    if "Node" not in df.columns or "Network" not in df.columns:
        return False, "Colonnes 'Node' ou 'Network' absentes dans la table des routes.", [
            "Colonnes nécessaires absentes ('Node' ou 'Network')."
        ]

    df["Network_str"] = df["Network"].astype(str)

    if "Protocol" in df.columns:
        df["Protocol_str"] = df["Protocol"].astype(str).str.lower()
    else:
        df["Protocol_str"] = ""

    if "Next_Hop" in df.columns:
        df["Next_Hop_str"] = df["Next_Hop"].astype(str)
    else:
        df["Next_Hop_str"] = ""

    missing_desc = []

    for exp in expected_static_routes:
        node = exp.get("node")
        net = exp.get("network")
        nh_ip = exp.get("next_hop_ip")

        if not node or not net:
            missing_desc.append(f"Entrée mal définie (node ou network manquant) : {exp}")
            continue

        subset = df[(df["Node"] == node) & (df["Network_str"] == str(net))]

        if nh_ip:
            subset = subset[subset["Next_Hop_str"].str.contains(str(nh_ip), na=False)]

        if "Protocol_str" in subset.columns:
            subset = subset[subset["Protocol_str"] == "static"]

        if subset.empty:
            missing_desc.append(f"{node}: {net} via {nh_ip or '?'} (static)")

    if missing_desc:
        msg = "Routes manquantes:\n      - " + "\n      - ".join(missing_desc)
        return False, msg, missing_desc

    msg = f"Toutes les routes attendues sont présentes ({len(expected_static_routes)})."
    return True, msg, []


def check_no_default_route(routes_df):
    """
    Vérifie l'absence de 0.0.0.0/0.
    Retourne (ok: bool, message: str, found_defaults: [dict]).
    """
    if routes_df is None or routes_df.empty or "Network" not in routes_df.columns:
        return True, "Pas de table de routage exploitable, test ignoré.", []

    df = routes_df.copy()
    df["Network_str"] = df["Network"].astype(str)

    bad = df[df["Network_str"] == "0.0.0.0/0"]

    if bad.empty:
        return True, "Aucune route 0.0.0.0/0 détectée.", []

    # Prépare une version sérialisable (Node, Vrf, Network, Next_Hop)
    cols = [c for c in ["Node", "Vrf", "Network", "Next_Hop"] if c in bad.columns]
    found = []
    for _, row in bad[cols].iterrows():
        entry = {}
        for c in cols:
            entry[c] = str(row.get(c))
        found.append(entry)

    msg = "Route(s) par défaut détectée(s)."
    return False, msg, found


def check_l3_edges_presence(edges_df):
    """
    Vérifie qu'il existe au moins une adjacency L3.
    Retourne (ok: bool, message: str, edges_count: int).
    """
    if edges_df is None or edges_df.empty:
        return False, "Aucune adjacency L3 détectée.", 0
    return True, f"{len(edges_df)} adjacency(s) L3 détectée(s).", len(edges_df)


def check_expected_l3_edges(edges_df, expected_l3_edges):
    """
    - Interface = "<node>[<iface>]"
    - Remote_Interface = "<remote_node>[<remote_iface>]"
    - IPs contient ip
    - Remote_IPs contient remote_ip

    Retourne (ok: bool, message: str, missing: [str]).
    """
    if not expected_l3_edges:
        return True, "Aucune adjacency attendue définie (test ignoré).", []

    if edges_df is None or edges_df.empty:
        return False, "Aucune adjacency L3 détectée.", [
            "Table des adjacences L3 vide, impossible de valider les adjacences attendues."
        ]

    df = edges_df.copy()

    for col in ["Interface", "Remote_Interface", "IPs", "Remote_IPs"]:
        if col in df.columns:
            df[col + "_str"] = df[col].astype(str)
        else:
            df[col + "_str"] = ""

    missing = []

    for exp in expected_l3_edges:
        node = exp.get("node")
        iface = exp.get("iface")
        rnode = exp.get("remote_node")
        riface = exp.get("remote_iface")
        ip = exp.get("ip")
        rip = exp.get("remote_ip")

        if not (node and iface and rnode and riface and ip and rip):
            missing.append(f"Entrée L3 mal définie : {exp}")
            continue

        if_name = f"{node}[{iface}]"
        remote_if_name = f"{rnode}[{riface}]"

        subset = df[
            (df["Interface_str"] == if_name)
            & (df["Remote_Interface_str"] == remote_if_name)
            & (df["IPs_str"].str.contains(str(ip), na=False))
            & (df["Remote_IPs_str"].str.contains(str(rip), na=False))
        ]

        if subset.empty:
            missing.append(
                f"{node}:{iface} ({ip}) <-> {rnode}:{riface} ({rip})"
            )

    if missing:
        msg = "Adjacences manquantes:\n      - " + "\n      - ".join(missing)
        return False, msg, missing

    msg = f"Toutes les adjacences L3 attendues sont présentes ({len(expected_l3_edges)})."
    return True, msg, []


def run_module():
    module_args = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', required=True),
        network=dict(type='str', required=True),
        snapshot=dict(type='str', required=True),
        snapshot_dir=dict(type='str', required=True),
        expected_static_routes=dict(type='list', elements='dict', required=False, default=[]),
        check_no_default_route=dict(type='bool', required=False, default=True),
        expected_l3_edges=dict(type='list', elements='dict', required=False, default=[]),
    )

    result = dict(
        changed=False,
        tests_ok=False,
        tests_summary=[],
        details={},
        routes=[],
        l3_edges=[],
        raw_batfish_errors=[],
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if not HAS_PYBATFISH:
        module.fail_json(msg="Le module Python pybatfish est requis (pip install pybatfish).", **result)

    if module.check_mode:
        result['tests_ok'] = True
        result['tests_summary'].append(dict(
            name="Validation routes / L3 (check_mode)",
            ok=True,
            message="check_mode: tests non exécutés."
        ))
        module.exit_json(**result)

    host = module.params['host']
    port = module.params['port']
    network = module.params['network']
    snapshot = module.params['snapshot']
    snapshot_dir = module.params['snapshot_dir']
    expected_static_routes = module.params['expected_static_routes'] or []
    check_default = module.params['check_no_default_route']
    expected_l3_edges = module.params['expected_l3_edges'] or []

    try:
        # Session Batfish
        bf = Session(host=host, port_v2=port, ssl=False)
        bf.set_network(network)
        bf.init_snapshot(snapshot_dir, name=snapshot, overwrite=True)
        bf.set_snapshot(snapshot)

        # Récupération routes()
        try:
            routes_df = bf.q.routes().answer().frame()
        except Exception as e:
            result["raw_batfish_errors"].append(f"Erreur routes(): {e}")
            module.fail_json(msg=f"Erreur lors de la récupération des routes via Batfish: {e}", **result)

        # Sérialisation de la RIB complète (tout en str)
        result["routes"] = _df_to_records_str(routes_df)

        # Récupération layer3Edges()
        try:
            edges_df = bf.q.layer3Edges().answer().frame()
        except Exception as e:
            result["raw_batfish_errors"].append(f"Erreur layer3Edges(): {e}")
            edges_df = None

        # Sérialisation L3 (tout en str)
        result["l3_edges"] = _df_to_records_str(edges_df)

        details = {}
        summaries = []

        # Test routes statiques attendues
        ok_static, msg_static, missing_static = check_expected_static_routes(routes_df, expected_static_routes)
        details["expected_static_routes"] = dict(
            ok=ok_static,
            message=msg_static,
            missing=missing_static,
        )
        summaries.append(dict(
            name="Routes statiques attendues présentes",
            ok=ok_static,
            message=msg_static,
        ))

        # Test absence de default route
        if check_default:
            ok_def, msg_def, found_defaults = check_no_default_route(routes_df)
            details["no_default_route"] = dict(
                ok=ok_def,
                message=msg_def,
                found_defaults=found_defaults,
            )
            summaries.append(dict(
                name="Absence de route par défaut 0.0.0.0/0",
                ok=ok_def,
                message=msg_def,
            ))

        # Présence d'au moins une adjacency L3
        ok_l3_presence, msg_l3_presence, edges_count = check_l3_edges_presence(edges_df)
        details["l3_edges_presence"] = dict(
            ok=ok_l3_presence,
            message=msg_l3_presence,
            edges_count=edges_count,
        )
        summaries.append(dict(
            name="Présence d'au moins une adjacency L3",
            ok=ok_l3_presence,
            message=msg_l3_presence,
        ))

        # Adj L3 attendues
        ok_l3_expected, msg_l3_expected, missing_l3 = check_expected_l3_edges(edges_df, expected_l3_edges)
        details["expected_l3_edges"] = dict(
            ok=ok_l3_expected,
            message=msg_l3_expected,
            missing=missing_l3,
        )
        summaries.append(dict(
            name="Adjacences L3 attendues présentes (interfaces + IP)",
            ok=ok_l3_expected,
            message=msg_l3_expected,
        ))

        # Statut global
        all_ok = all(s["ok"] for s in summaries) if summaries else True

        result["tests_ok"] = all_ok
        result["details"] = details
        result["tests_summary"] = summaries

        module.exit_json(**result)

    except Exception as e:
        result["raw_batfish_errors"].append(str(e))
        # ici result ne contient plus d'objets exotiques, donc fail_json est safe
        module.fail_json(msg=f"Erreur lors de la validation Batfish (routes/L3): {e}", **result)


def main():
    run_module()


if __name__ == '__main__':
    main()

