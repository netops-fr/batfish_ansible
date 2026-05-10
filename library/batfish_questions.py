#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: batfish_questions

short_description: Exécute des questions d'inventaire Batfish (routes, interfaces, parse, etc.).

version_added: "1.0.0"

description: >
  Se connecte à un serveur Batfish et exécute un ensemble de questions
  de diagnostic / inventaire (fileParseStatus, parseWarning, nodeProperties,
  interfaceProperties, ipOwners, layer3Edges, routes, searchFilters()).
  Utile pour générer des faits ou du debug dans des playbooks.

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

  file_parse_status:
    description: Exécuter fileParseStatus().
    required: false
    type: bool
    default: false

  parse_warning:
    description: Exécuter parseWarning() et renvoyer une synthèse.
    required: false
    type: bool
    default: false

  node_properties:
    description: Exécuter nodeProperties().
    required: false
    type: bool
    default: false

  interface_properties:
    description: Exécuter interfaceProperties().
    required: false
    type: bool
    default: false

  ip_owners:
    description: Exécuter ipOwners().
    required: false
    type: bool
    default: false

  layer3_edges:
    description: Exécuter layer3Edges().
    required: false
    type: bool
    default: false

  routes:
    description: Exécuter routes() et renvoyer la RIB + une petite synthèse.
    required: false
    type: bool
    default: false

  search_filters_dump:
    description: >
      Exécuter searchFilters() (sans contraintes) et renvoyer le résultat.
      Attention, peut être volumineux; résultat éventuellement tronqué.
    required: false
    type: bool
    default: false

  search_filters_max_rows:
    description: Nombre maximum de lignes à renvoyer pour searchFilters().
    required: false
    type: int
    default: 100

author:
  - "Toi :)"
'''

EXAMPLES = r'''
- name: Poser quelques questions Batfish
  batfish_questions:
    host: 127.0.0.1
    port: 9996
    network: fortigate_lab
    snapshot: fortigate_snapshot_01
    snapshot_dir: /root/netops.fr/article/batfish/batfish/snapshot_fortigate
    node_properties: true
    interface_properties: true
    routes: true
  register: bf_q

- name: Voir les routes
  debug:
    var: bf_q.routes

- name: Voir la synthèse routes
  debug:
    var: bf_q.routes_summary

- name: Lancer un dump searchFilters pour debug
  batfish_questions:
    host: 127.0.0.1
    port: 9996
    network: fortigate_lab
    snapshot: fortigate_snapshot_01
    snapshot_dir: /root/netops.fr/article/batfish/batfish/snapshot_fortigate
    search_filters_dump: true
    search_filters_max_rows: 50
  register: bf_filters

- name: Afficher le dump searchFilters
  debug:
    var: bf_filters.search_filters
'''

RETURN = r'''
file_parse_status:
  description: Résultat brut de fileParseStatus() (liste de dict) ou null.
  type: list
  elements: dict
  returned: when requested

parse_warning_summary:
  description: Synthèse par fichier (Filename, Warning_Count) ou null.
  type: list
  elements: dict
  returned: when requested

parse_warning_top_contexts:
  description: Top des Parser_Context les plus fréquents ou null.
  type: list
  elements: dict
  returned: when requested

parse_warning_examples:
  description: Exemples de warnings (quelques lignes) ou null.
  type: list
  elements: dict
  returned: when requested

node_properties:
  description: Résultat brut de nodeProperties() (liste de dict) ou null.
  type: list
  elements: dict
  returned: when requested

interface_properties:
  description: Résultat brut de interfaceProperties() (liste de dict) ou null.
  type: list
  elements: dict
  returned: when requested

ip_owners:
  description: Résultat brut de ipOwners() (liste de dict) ou null.
  type: list
  elements: dict
  returned: when requested

layer3_edges:
  description: Résultat brut de layer3Edges() (liste de dict) ou null.
  type: list
  elements: dict
  returned: when requested

routes:
  description: Table de routage complète vue par Batfish (liste de dict) ou null.
  type: list
  elements: dict
  returned: when requested

routes_summary:
  description: Synthèse des routes par Node/Vrf (Route_Count, Protocols) ou null.
  type: list
  elements: dict
  returned: when requested

search_filters:
  description: Résultat de searchFilters() (eventuellement tronqué) ou null.
  type: list
  elements: dict
  returned: when requested

raw_batfish_errors:
  description: Liste des erreurs rencontrées pour certaines questions.
  type: list
  elements: str
  returned: always
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from pybatfish.client.session import Session
    HAS_PYBATFISH = True
except Exception:
    HAS_PYBATFISH = False


def _df_to_records(df, max_rows=None):
    """
    Convertit un DataFrame Batfish en liste de dict JSON-serializable.
    On force tout en string pour éviter les types pybatfish non gérés
    (Interface, Flow, Ip, etc.) par Ansible.
    """
    if df is None:
        return None
    df = df.copy()
    if max_rows is not None:
        df = df.head(max_rows)
    # Cast de toutes les colonnes en str pour éviter les types custom
    for col in df.columns:
        df[col] = df[col].astype(str)
    return df.to_dict(orient="records")


def run_module():
    module_args = dict(
        host=dict(type='str', required=True),
        port=dict(type='int', required=True),
        network=dict(type='str', required=True),
        snapshot=dict(type='str', required=True),
        snapshot_dir=dict(type='str', required=True),

        file_parse_status=dict(type='bool', required=False, default=False),
        parse_warning=dict(type='bool', required=False, default=False),
        node_properties=dict(type='bool', required=False, default=False),
        interface_properties=dict(type='bool', required=False, default=False),
        ip_owners=dict(type='bool', required=False, default=False),
        layer3_edges=dict(type='bool', required=False, default=False),
        routes=dict(type='bool', required=False, default=False),
        search_filters_dump=dict(type='bool', required=False, default=False),
        search_filters_max_rows=dict(type='int', required=False, default=100),
    )

    result = dict(
        changed=False,
        file_parse_status=None,
        parse_warning_summary=None,
        parse_warning_top_contexts=None,
        parse_warning_examples=None,
        node_properties=None,
        interface_properties=None,
        ip_owners=None,
        layer3_edges=None,
        routes=None,
        routes_summary=None,
        search_filters=None,
        raw_batfish_errors=[],
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if not HAS_PYBATFISH:
        module.fail_json(msg="Le module Python pybatfish est requis (pip install pybatfish).", **result)

    if module.check_mode:
        module.exit_json(**result)

    host = module.params['host']
    port = module.params['port']
    network = module.params['network']
    snapshot = module.params['snapshot']
    snapshot_dir = module.params['snapshot_dir']

    do_file_parse_status = module.params['file_parse_status']
    do_parse_warning = module.params['parse_warning']
    do_node_prop = module.params['node_properties']
    do_iface_prop = module.params['interface_properties']
    do_ip_owners = module.params['ip_owners']
    do_l3_edges = module.params['layer3_edges']
    do_routes = module.params['routes']
    do_search_filters = module.params['search_filters_dump']
    sf_max = module.params['search_filters_max_rows']

    try:
        bf = Session(host=host, port_v2=port, ssl=False)
        bf.set_network(network)
        bf.init_snapshot(snapshot_dir, name=snapshot, overwrite=True)
        bf.set_snapshot(snapshot)
    except Exception as e:
        result["raw_batfish_errors"].append(f"Erreur initialisation session/snapshot: {e}")
        module.fail_json(msg=f"Erreur lors de l'initialisation Batfish: {e}", **result)

    # fileParseStatus
    if do_file_parse_status:
        try:
            df = bf.q.fileParseStatus().answer().frame()
            result["file_parse_status"] = _df_to_records(df)
        except Exception as e:
            result["raw_batfish_errors"].append(f"fileParseStatus(): {e}")
            result["file_parse_status"] = None

    # parseWarning
    if do_parse_warning:
        try:
            pw_df = bf.q.parseWarning().answer().frame()
            if pw_df is None or pw_df.empty:
                result["parse_warning_summary"] = []
                result["parse_warning_top_contexts"] = []
                result["parse_warning_examples"] = []
            else:
                # Synthèse par fichier
                if "Filename" in pw_df.columns:
                    by_file = pw_df.groupby("Filename").size().reset_index(name="Warning_Count")
                    result["parse_warning_summary"] = _df_to_records(by_file)
                else:
                    result["parse_warning_summary"] = []

                # Top contexts
                if "Parser_Context" in pw_df.columns:
                    by_ctx = (
                        pw_df.groupby("Parser_Context")
                        .size()
                        .reset_index(name="Count")
                        .sort_values("Count", ascending=False)
                        .head(10)
                    )
                    result["parse_warning_top_contexts"] = _df_to_records(by_ctx)
                else:
                    result["parse_warning_top_contexts"] = []

                # Exemples
                cols = [c for c in ["Filename", "Line", "Text", "Parser_Context", "Comment"] if c in pw_df.columns]
                examples = pw_df[cols].head(30) if cols else pw_df.head(30)
                result["parse_warning_examples"] = _df_to_records(examples)
        except Exception as e:
            result["raw_batfish_errors"].append(f"parseWarning(): {e}")
            result["parse_warning_summary"] = None
            result["parse_warning_top_contexts"] = None
            result["parse_warning_examples"] = None

    # nodeProperties
    if do_node_prop:
        try:
            df = bf.q.nodeProperties().answer().frame()
            result["node_properties"] = _df_to_records(df)
        except Exception as e:
            result["raw_batfish_errors"].append(f"nodeProperties(): {e}")
            result["node_properties"] = None

    # interfaceProperties
    if do_iface_prop:
        try:
            df = bf.q.interfaceProperties().answer().frame()
            result["interface_properties"] = _df_to_records(df)
        except Exception as e:
            result["raw_batfish_errors"].append(f"interfaceProperties(): {e}")
            result["interface_properties"] = None

    # ipOwners
    if do_ip_owners:
        try:
            df = bf.q.ipOwners().answer().frame()
            result["ip_owners"] = _df_to_records(df)
        except Exception as e:
            result["raw_batfish_errors"].append(f"ipOwners(): {e}")
            result["ip_owners"] = None

    # layer3Edges
    if do_l3_edges:
        try:
            df = bf.q.layer3Edges().answer().frame()
            result["layer3_edges"] = _df_to_records(df)
        except Exception as e:
            result["raw_batfish_errors"].append(f"layer3Edges(): {e}")
            result["layer3_edges"] = None

    # routes
    if do_routes:
        try:
            r_df = bf.q.routes().answer().frame()
            if r_df is None or r_df.empty:
                result["routes"] = []
                result["routes_summary"] = []
            else:
                # RIB brute
                r_df = r_df.copy()
                if "Network" in r_df.columns:
                    r_df["Network"] = r_df["Network"].astype(str)
                result["routes"] = _df_to_records(r_df)

                # Synthèse par Node/Vrf
                group_cols = [c for c in ["Node", "Vrf"] if c in r_df.columns]
                if group_cols:
                    agg_dict = {"Route_Count": ("Network", "count")}
                    if "Protocol" in r_df.columns:
                        agg_dict["Protocols"] = (
                            "Protocol",
                            lambda x: ", ".join(sorted(set(map(str, x)))),
                        )
                    summary = r_df.groupby(group_cols).agg(**agg_dict).reset_index()
                    result["routes_summary"] = _df_to_records(summary)
                else:
                    result["routes_summary"] = []
        except Exception as e:
            result["raw_batfish_errors"].append(f"routes(): {e}")
            result["routes"] = None
            result["routes_summary"] = None

    # searchFilters()
    if do_search_filters:
        try:
            sf_df = bf.q.searchFilters().answer().frame()
            if sf_df is None or sf_df.empty:
                result["search_filters"] = []
            else:
                result["search_filters"] = _df_to_records(sf_df, max_rows=sf_max)
        except Exception as e:
            result["raw_batfish_errors"].append(f"searchFilters(): {e}")
            result["search_filters"] = None

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

