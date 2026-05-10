#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: batfish_validate

short_description: Valider une topologie réseau avec Batfish

version_added: "1.0.0"

description:
  - Se connecte à un serveur Batfish.
  - Initialise un snapshot réseau local.
  - Charge un fichier C(params.yml).
  - Exécute des tests de validation réseau déclarés dans la section C(tests).
  - Tous les tests sont optionnels.
  - Un test non déclaré ou non activé est ignoré et renvoyé avec C(skipped=true).

requirements:
  - pybatfish
  - pyyaml

options:
  host:
    description:
      - Adresse IP ou nom DNS du serveur Batfish.
    required: true
    type: str

  port:
    description:
      - Port HTTP v2 du serveur Batfish.
      - Généralement C(9996).
    required: true
    type: int

  network:
    description:
      - Nom logique du réseau Batfish.
      - Correspond à C(bf.set_network()).
    required: true
    type: str

  snapshot:
    description:
      - Nom logique du snapshot Batfish.
      - Correspond au paramètre C(name) de C(bf.init_snapshot()).
    required: true
    type: str

  snapshot_dir:
    description:
      - Chemin local du snapshot Batfish.
      - Le dossier doit contenir un sous-dossier C(configs/).
    required: true
    type: str

  params_file:
    description:
      - Chemin du fichier YAML de paramètres.
      - Ce fichier contient la section C(tests).
      - Si aucun fichier n'est fourni, tous les tests déclaratifs sont ignorés.
    required: false
    type: str

notes:
  - Le module ne modifie pas les équipements réseau.
  - Le module initialise ou réinitialise le snapshot Batfish avec C(overwrite=True).
  - Le module ne fait pas échouer directement le playbook si un test échoue.
  - Le statut global est renvoyé dans C(tests_ok).
  - Le playbook peut ensuite décider d'échouer avec C(when: not bf_result.tests_ok).

author:
  - "Toi :)"
'''






EXAMPLES = r'''
- name: Validation Batfish d'un snapshot Nexus
  batfish_validate:
    host: 127.0.0.1
    port: 9996
    network: nexus_lab
    snapshot: nexus_snapshot_01
    snapshot_dir: /root/lab_netbox/batfish/nexus_snapshot_01
    params_file: /root/lab_netbox/batfish/params.yml
  register: bf_result

- name: Afficher le résumé des tests
  debug:
    var: bf_result.tests_summary

- name: Afficher les détails reachability
  debug:
    var: bf_result.reachability_details
  when:
    - bf_result.reachability_details is defined
    - bf_result.reachability_details | length > 0

- name: Afficher les détails filters/policies
  debug:
    var: bf_result.filter_tests_details
  when:
    - bf_result.filter_tests_details is defined
    - bf_result.filter_tests_details | length > 0

- name: Echouer si la validation Batfish est KO
  fail:
    msg: "Validation Batfish échouée, voir bf_result.tests_summary"
  when:
    - bf_result.tests_ok is defined
    - not bf_result.tests_ok
'''









RETURN = r'''
tests_ok:
  description:
    - Indique si tous les tests exécutés sont passés.
    - Les tests ignorés sont considérés comme OK.
  type: bool
  returned: always
  sample: true

tests_summary:
  description:
    - Liste synthétique des tests exécutés ou ignorés.
    - Chaque entrée contient au minimum C(name), C(ok), C(skipped) et C(message).
  type: list
  elements: dict
  returned: always
  sample:
    - name: "Routes statiques attendues présentes"
      ok: true
      skipped: false
      message: "Toutes les routes attendues sont présentes (1)."
    - name: "Absence de route par défaut 0.0.0.0/0"
      ok: true
      skipped: true
      message: "Test no_default_route non activé (test ignoré)."

reachability_details:
  description:
    - Détail des tests de reachability L3 déclarés dans C(tests.reachability_flows).
    - Vide si aucun test de reachability n'est déclaré.
  type: list
  elements: dict
  returned: always
  sample:
    - name: "HTTP client vers serveur"
      src: "10.0.10.1"
      dst: "10.0.20.1"
      protocol: "tcp"
      bidirectional: false
      forward:
        ok: true
        paths: 1
      backward: {}

filter_tests_details:
  description:
    - Détail des tests de filters/policies déclarés dans C(tests.filter_tests.flows).
    - Vide si aucun test de filter/policy n'est déclaré.
  type: list
  elements: dict
  returned: always
  sample:
    - name: "Flux HTTP autorisé"
      src: "10.0.10.1"
      dst: "10.0.20.1"
      protocol: "tcp"
      dst_port: 80
      expected_action: "permit"
      node: "fw01"
      filter_pattern: "POLICY_"
      matches: []
      actions_observed:
        - "PERMIT"
      ok: true
      error: null

raw_batfish_errors:
  description:
    - Liste des erreurs rencontrées pendant les requêtes Batfish non bloquantes.
    - Par exemple une erreur lors de C(bf.q.routes()).
  type: list
  elements: str
  returned: always
  sample:
    - "Erreur bf.q.routes(): ..."
'''









# --------------------------------------------------------------------
# Format attendu du fichier params.yml
# --------------------------------------------------------------------
#
# tests:
#   # Optionnel.
#   # Si absent ou vide, le test est ignoré.
#   expected_static_routes:
#     - node: "sw1-lab"
#       network: "20.0.0.0/8"
#       next_hop_ip: "10.4.0.254"
#
#   # Optionnel.
#   # false par défaut.
#   # true => échoue si une route 0.0.0.0/0 est présente.
#   no_default_route: false
#
#   # Optionnel.
#   # false par défaut.
#   # true => échoue si aucune adjacency L3 n'est détectée.
#   require_l3_edges: false
#
#   # Optionnel.
#   # false par défaut.
#   # true => échoue si ipOwners() est vide.
#   require_ip_owners: false
#
#   # Optionnel.
#   # Si absent ou vide, le test est ignoré.
#   expected_l3_edges:
#     - node: "sw1-lab"
#       iface: "Vlan400"
#       ip: "10.4.0.1"
#       remote_node: "r1"
#       remote_iface: "Ethernet0"
#       remote_ip: "10.4.0.254"
#
#   # Optionnel.
#   # Si absent ou vide, le test est ignoré.
#   reachability_flows:
#     - name: "HTTP client vers serveur"
#       src: "10.0.10.1"
#       dst: "10.0.20.1"
#       protocol: "tcp"
#       src_port: 12345
#       dst_port: 80
#       bidirectional: false
#       start_location: "sw1-lab"
#
#   # Optionnel.
#   # Si absent ou vide, le test est ignoré.
#   filter_tests:
#     flows:
#       - name: "Flux HTTP autorisé"
#         src: "10.0.10.1"
#         dst: "10.0.20.1"
#         protocol: "tcp"
#         dst_port: 80
#         expected_action: "permit"
#         node: "fw01"
#         filter: "POLICY_"
#
# Tests actuellement supportés :
#
# 1. expected_static_routes
#    Vérifie que les routes statiques attendues existent.
#
# 2. no_default_route
#    Vérifie l'absence de route 0.0.0.0/0.
#    Désactivé par défaut.
#
# 3. require_l3_edges
#    Vérifie qu'au moins une adjacency L3 existe.
#    Désactivé par défaut.
#
# 4. expected_l3_edges
#    Vérifie des adjacences L3 précises.
#
# 5. require_ip_owners
#    Vérifie que Batfish détecte au moins une IP portée par une interface.
#    Désactivé par défaut.
#
# 6. reachability_flows
#    Vérifie que des flux L3 sont atteignables.
#
# 7. filter_tests.flows
#    Vérifie des flux au niveau des filters/policies Batfish.
# --------------------------------------------------------------------















from ansible.module_utils.basic import AnsibleModule

import os
import sys

try:
    from pybatfish.client.session import Session
    from pybatfish.datamodel.flow import HeaderConstraints
except ImportError as e:
    BATFISH_IMPORT_ERROR = e
else:
    BATFISH_IMPORT_ERROR = None

try:
    import yaml
except ImportError as e:
    YAML_IMPORT_ERROR = e
else:
    YAML_IMPORT_ERROR = None


CONFIG = {}
TESTS_CFG = {}

EXPECTED_STATIC_ROUTES = []
EXPECTED_L3_EDGES = []
EXPECTED_REACHABILITY_FLOWS = []
FILTER_TESTS_FLOWS = []


def load_config(params_file):
    global CONFIG, TESTS_CFG
    global EXPECTED_STATIC_ROUTES, EXPECTED_L3_EDGES
    global EXPECTED_REACHABILITY_FLOWS, FILTER_TESTS_FLOWS

    CONFIG = {}
    TESTS_CFG = {}

    EXPECTED_STATIC_ROUTES = []
    EXPECTED_L3_EDGES = []
    EXPECTED_REACHABILITY_FLOWS = []
    FILTER_TESTS_FLOWS = []

    if not params_file:
        return

    if not os.path.isabs(params_file):
        params_file = os.path.abspath(params_file)

    if not os.path.exists(params_file):
        raise FileNotFoundError("params_file introuvable: %s" % params_file)

    with open(params_file, "r") as f:
        CONFIG = yaml.safe_load(f) or {}

    TESTS_CFG = CONFIG.get("tests", {}) or {}

    EXPECTED_STATIC_ROUTES = TESTS_CFG.get("expected_static_routes", []) or []
    EXPECTED_L3_EDGES = TESTS_CFG.get("expected_l3_edges", []) or []
    EXPECTED_REACHABILITY_FLOWS = TESTS_CFG.get("reachability_flows", []) or []

    filter_tests = TESTS_CFG.get("filter_tests", {}) or {}
    FILTER_TESTS_FLOWS = filter_tests.get("flows", []) or []


def _skipped(name, message):
    return {
        "name": name,
        "ok": True,
        "skipped": True,
        "message": message,
    }


def _test_expected_static_routes(routes_df):
    name = "Routes statiques attendues présentes"

    if not EXPECTED_STATIC_ROUTES:
        return _skipped(name, "Aucune route attendue définie (test ignoré).")

    if routes_df is None or routes_df.empty:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": "Aucune route disponible dans Batfish.",
        }

    df = routes_df.copy()

    if "Node" not in df.columns or "Network" not in df.columns:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": "Colonnes 'Node' ou 'Network' absentes dans la table des routes.",
        }

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

    for exp in EXPECTED_STATIC_ROUTES:
        node = exp["node"]
        net = exp["network"]
        nh_ip = exp.get("next_hop_ip")

        subset = df[(df["Node"] == node) & (df["Network_str"] == net)]

        if nh_ip:
            subset = subset[subset["Next_Hop_str"].str.contains(nh_ip, na=False)]

        if "Protocol_str" in subset.columns:
            subset = subset[subset["Protocol_str"] == "static"]

        if subset.empty:
            missing_desc.append(f"{node}: {net} via {nh_ip or '?'} (static)")

    if missing_desc:
        msg = "Routes manquantes: " + "; ".join(missing_desc)
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": msg,
        }

    return {
        "name": name,
        "ok": True,
        "skipped": False,
        "message": f"Toutes les routes attendues sont présentes ({len(EXPECTED_STATIC_ROUTES)}).",
    }


def _test_no_default_route(routes_df):
    name = "Absence de route par défaut 0.0.0.0/0"

    if not TESTS_CFG.get("no_default_route", False):
        return _skipped(name, "Test no_default_route non activé (test ignoré).")

    if routes_df is None or routes_df.empty or "Network" not in routes_df.columns:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": "Pas de table de routage exploitable.",
        }

    df = routes_df.copy()
    df["Network_str"] = df["Network"].astype(str)

    bad = df[df["Network_str"] == "0.0.0.0/0"]

    if bad.empty:
        return {
            "name": name,
            "ok": True,
            "skipped": False,
            "message": "Aucune route 0.0.0.0/0 détectée.",
        }

    cols = [c for c in ["Node", "Vrf", "Network_str", "Next_Hop"] if c in bad.columns]
    lines = bad[cols].to_string(index=False)

    return {
        "name": name,
        "ok": False,
        "skipped": False,
        "message": f"Route(s) par défaut détectée(s):\n{lines}",
    }


def _test_layer3_edges(bf):
    name = "Présence d'au moins une adjacency L3"

    if not TESTS_CFG.get("require_l3_edges", False):
        return _skipped(name, "Test require_l3_edges non activé (test ignoré).")

    try:
        edges = bf.q.layer3Edges().answer().frame()
    except Exception as e:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": f"Échec de la requête layer3Edges(): {e}",
        }

    if edges is None or edges.empty:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": "Aucune adjacency L3 détectée.",
        }

    return {
        "name": name,
        "ok": True,
        "skipped": False,
        "message": f"{len(edges)} adjacency(s) L3 détectée(s).",
    }


def _test_expected_l3_edges(bf):
    name = "Adjacences L3 attendues présentes (interfaces + IP)"

    if not EXPECTED_L3_EDGES:
        return _skipped(name, "Aucune adjacency attendue définie (test ignoré).")

    try:
        edges = bf.q.layer3Edges().answer().frame()
    except Exception as e:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": f"Échec de la requête layer3Edges(): {e}",
        }

    if edges is None or edges.empty:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": "Aucune adjacency L3 détectée.",
        }

    df = edges.copy()

    for col in ["Interface", "Remote_Interface", "IPs", "Remote_IPs"]:
        if col in df.columns:
            df[col + "_str"] = df[col].astype(str)
        else:
            df[col + "_str"] = ""

    missing = []

    for exp in EXPECTED_L3_EDGES:
        if_name = f"{exp['node']}[{exp['iface']}]"
        remote_if_name = f"{exp['remote_node']}[{exp['remote_iface']}]"
        ip = exp["ip"]
        rip = exp["remote_ip"]

        subset = df[
            (df["Interface_str"] == if_name)
            & (df["Remote_Interface_str"] == remote_if_name)
            & (df["IPs_str"].str.contains(ip, na=False))
            & (df["Remote_IPs_str"].str.contains(rip, na=False))
        ]

        if subset.empty:
            missing.append(
                f"{exp['node']}:{exp['iface']} ({ip}) <-> "
                f"{exp['remote_node']}:{exp['remote_iface']} ({rip})"
            )

    if missing:
        msg = "Adjacences manquantes: " + "; ".join(missing)
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": msg,
        }

    return {
        "name": name,
        "ok": True,
        "skipped": False,
        "message": f"Toutes les adjacences L3 attendues sont présentes ({len(EXPECTED_L3_EDGES)}).",
    }


def _test_ip_owners(bf):
    name = "Présence d'IP associées à des interfaces (ipOwners)"

    if not TESTS_CFG.get("require_ip_owners", False):
        return _skipped(name, "Test require_ip_owners non activé (test ignoré).")

    try:
        df = bf.q.ipOwners().answer().frame()
    except Exception as e:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": f"Échec de la requête ipOwners(): {e}",
        }

    if df is None or df.empty:
        return {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": "ipOwners() est vide.",
        }

    return {
        "name": name,
        "ok": True,
        "skipped": False,
        "message": f"{len(df)} IP possédées par des interfaces.",
    }


def _test_reachability_flows(bf):
    name = "Reachability L3 des flux attendus (chemins logiques)"
    details = []

    if not EXPECTED_REACHABILITY_FLOWS:
        summary = _skipped(name, "Aucun test de reachability défini (test ignoré).")
        return summary, details

    errors = []

    for flow in EXPECTED_REACHABILITY_FLOWS:
        desc = flow.get("name") or f"{flow.get('src')} -> {flow.get('dst')}"
        src = flow.get("src")
        dst = flow.get("dst")
        proto = (flow.get("protocol") or "icmp").lower()
        bidir = bool(flow.get("bidirectional", False))

        item = {
            "name": desc,
            "src": src,
            "dst": dst,
            "protocol": proto,
            "bidirectional": bidir,
            "forward": {},
            "backward": {},
        }

        if not src or not dst:
            msg = "config incomplète (src/dst manquant)"
            item["forward"] = {"ok": False, "paths": 0, "error": msg}
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        try:
            headers_kwargs = {
                "srcIps": src,
                "dstIps": dst,
                "ipProtocols": [proto],
            }

            if flow.get("src_port") is not None:
                headers_kwargs["srcPorts"] = [int(flow.get("src_port"))]
            if flow.get("dst_port") is not None:
                headers_kwargs["dstPorts"] = [int(flow.get("dst_port"))]

            headers = HeaderConstraints(**headers_kwargs)

            q_kwargs = {"headers": headers}

            if flow.get("start_location"):
                q_kwargs["startLocation"] = flow.get("start_location")

            df = bf.q.reachability(**q_kwargs).answer().frame()
        except Exception as e:
            msg = f"erreur reachability() aller: {e}"
            item["forward"] = {"ok": False, "paths": 0, "error": str(e)}
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        if df is None or df.empty:
            msg = f"AUCUN chemin trouvé (sens {src} -> {dst})"
            item["forward"] = {"ok": False, "paths": 0, "error": msg}
            errors.append(f"{desc}: {msg}")
        else:
            item["forward"] = {
                "ok": True,
                "paths": int(len(df)),
            }

        if bidir:
            try:
                headers_back = HeaderConstraints(
                    srcIps=dst,
                    dstIps=src,
                    ipProtocols=[proto],
                )
                df_back = bf.q.reachability(headers=headers_back).answer().frame()
            except Exception as e:
                msg = f"erreur reachability() retour: {e}"
                item["backward"] = {"ok": False, "paths": 0, "error": str(e)}
                errors.append(f"{desc}: {msg}")
            else:
                if df_back is None or df_back.empty:
                    msg = f"AUCUN chemin trouvé (sens {dst} -> {src})"
                    item["backward"] = {"ok": False, "paths": 0, "error": msg}
                    errors.append(f"{desc}: {msg}")
                else:
                    item["backward"] = {
                        "ok": True,
                        "paths": int(len(df_back)),
                    }

        details.append(item)

    if errors:
        msg = "Flux de reachability L3 NON conformes: " + "; ".join(errors)
        summary = {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": msg,
        }
    else:
        summary = {
            "name": name,
            "ok": True,
            "skipped": False,
            "message": f"Tous les flux de reachability L3 sont atteignables ({len(EXPECTED_REACHABILITY_FLOWS)}).",
        }

    return summary, details


def _test_filter_policies(bf):
    name = "Vérification des flux au niveau des filters (policies)"
    details = []

    if not FILTER_TESTS_FLOWS:
        summary = _skipped(name, "Aucun test de filters défini (test ignoré).")
        return summary, details

    errors = []

    for flt in FILTER_TESTS_FLOWS:
        desc = flt.get("name") or f"{flt.get('src')} -> {flt.get('dst')}"
        src = flt.get("src")
        dst = flt.get("dst")
        proto = (flt.get("protocol") or "tcp").lower()
        src_port = flt.get("src_port")
        dst_port = flt.get("dst_port")
        expected_action = (flt.get("expected_action") or "permit").lower()
        node = flt.get("node")
        filter_pattern = flt.get("filter")

        item = {
            "name": desc,
            "src": src,
            "dst": dst,
            "protocol": proto,
            "src_port": src_port,
            "dst_port": dst_port,
            "expected_action": expected_action,
            "node": node,
            "filter_pattern": filter_pattern,
            "matches": [],
            "actions_observed": [],
            "ok": False,
            "error": None,
        }

        if not src or not dst:
            msg = "config incomplète (src/dst manquant)"
            item["error"] = msg
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        headers_kwargs = {
            "srcIps": src,
            "dstIps": dst,
            "ipProtocols": [proto],
        }

        if src_port is not None:
            headers_kwargs["srcPorts"] = [int(src_port)]
        if dst_port is not None:
            headers_kwargs["dstPorts"] = [int(dst_port)]

        headers = HeaderConstraints(**headers_kwargs)

        try:
            q_kwargs = {
                "headers": headers,
                "action": expected_action,
            }

            if node:
                q_kwargs["nodes"] = node

            df = bf.q.searchFilters(**q_kwargs).answer().frame()
        except Exception as e:
            msg = f"erreur searchFilters(): {e}"
            item["error"] = str(e)
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        if df is None or df.empty:
            msg = "searchFilters() n'a retourné aucun résultat pour ces headers."
            item["error"] = msg
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        if "Node" in df.columns:
            df["Node"] = df["Node"].astype(str)
        if "Filter_Name" in df.columns:
            df["Filter_Name"] = df["Filter_Name"].astype(str)
        if "Trace" in df.columns:
            df["Trace"] = df["Trace"].astype(str)
        if "Action" in df.columns:
            df["Action"] = df["Action"].astype(str).str.upper()

        if node and "Node" in df.columns:
            df = df[df["Node"] == node]

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

        if df is None or df.empty:
            msg = "Aucune ligne après filtrage node/policy/motif."
            item["error"] = msg
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        cols_to_show = [c for c in ["Node", "Filter_Name", "Action", "Trace"] if c in df.columns]

        for _, row in df[cols_to_show].iterrows():
            item["matches"].append({k: row[k] for k in cols_to_show})

        if "Action" not in df.columns:
            msg = "colonne 'Action' absente du résultat searchFilters()."
            item["error"] = msg
            errors.append(f"{desc}: {msg}")
            details.append(item)
            continue

        observed_actions = sorted(set(df["Action"]))
        item["actions_observed"] = observed_actions

        if expected_action.upper() in observed_actions:
            item["ok"] = True
        else:
            msg = (
                f"action attendue '{expected_action}' NON trouvée "
                f"(actions observées : {', '.join(observed_actions)})"
            )
            item["error"] = msg
            errors.append(f"{desc}: {msg}")

        details.append(item)

    if errors:
        msg = "Flux NON conformes aux filters selon Batfish: " + "; ".join(errors)
        summary = {
            "name": name,
            "ok": False,
            "skipped": False,
            "message": msg,
        }
    else:
        summary = {
            "name": name,
            "ok": True,
            "skipped": False,
            "message": f"Tous les tests de filters sont conformes ({len(FILTER_TESTS_FLOWS)}).",
        }

    return summary, details


def run_module():
    module_args = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', required=True),
        network=dict(type='str', required=True),
        snapshot=dict(type='str', required=True),
        snapshot_dir=dict(type='str', required=True),
        params_file=dict(type='str', required=False, default=None),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if BATFISH_IMPORT_ERROR is not None:
        module.fail_json(msg="Module pybatfish manquant: %s" % BATFISH_IMPORT_ERROR)

    if YAML_IMPORT_ERROR is not None:
        module.fail_json(msg="Module pyyaml manquant: %s" % YAML_IMPORT_ERROR)

    host = module.params["host"]
    port = module.params["port"]
    network = module.params["network"]
    snapshot = module.params["snapshot"]
    snapshot_dir = module.params["snapshot_dir"]
    params_file = module.params["params_file"]

    try:
        load_config(params_file)
    except Exception as e:
        module.fail_json(msg="Erreur lors du chargement de params_file: %s" % e)

    raw_errors = []

    try:
        bf = Session(
            host=host,
            port_v2=port,
            ssl=False,
        )

        bf.set_network(network)

        bf.init_snapshot(
            snapshot_dir,
            name=snapshot,
            overwrite=True,
        )

        bf.set_snapshot(snapshot)

        try:
            routes_df = bf.q.routes().answer().frame()
        except Exception as e:
            routes_df = None
            raw_errors.append("Erreur bf.q.routes(): %s" % e)

        tests = []

        tests.append(_test_expected_static_routes(routes_df))
        tests.append(_test_no_default_route(routes_df))

        tests.append(_test_layer3_edges(bf))
        tests.append(_test_expected_l3_edges(bf))
        tests.append(_test_ip_owners(bf))

        reach_summary, reach_details = _test_reachability_flows(bf)
        tests.append(reach_summary)

        filt_summary, filt_details = _test_filter_policies(bf)
        tests.append(filt_summary)

        tests_ok = all(t.get("ok", False) for t in tests)

        result = dict(
            changed=False,
            tests_ok=tests_ok,
            tests_summary=tests,
            reachability_details=reach_details,
            filter_tests_details=filt_details,
            raw_batfish_errors=raw_errors,
        )

        module.exit_json(**result)

    except Exception as e:
        module.fail_json(msg="Erreur lors de l'analyse Batfish: %s" % e)


def main():
    run_module()


if __name__ == '__main__':
    main()