#!/usr/bin/python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: batfish_validate_reachability

short_description: Valide la reachability L3 de flux définis via Batfish.

version_added: "1.0.0"

description: >
  Se connecte à un serveur Batfish, utilise la question reachability()
  pour vérifier que certains flux (ICMP/TCP/UDP...) sont atteignables
  (aller et éventuellement retour).
  Le module remonte tous les flows que Batfish retourne (Flow, Traces,
  Disposition, etc.) sans filtrer par action côté Batfish, puis considère
  qu'un flux est "OK" s'il existe au moins un flow avec une disposition
  de type succès (ACCEPTED / DELIVERED_TO_SUBNET / EXITS_NETWORK).

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
      Liste de flux à tester. Exemple d'entrée :

        - name: "Ping 10.0.0.1 -> 10.0.0.2"
          src: "10.0.0.1"
          dst: "10.0.0.2"
          protocol: "icmp"        # icmp|tcp|udp (par défaut: icmp)
          bidirectional: true     # par défaut: false
          src_port: 12345         # optionnel, pour TCP/UDP
          dst_port: 80            # optionnel, pour TCP/UDP
          start_location: "fortigat_ansible[port4]"  # optionnel (locationSpec)

        - name: "HTTP 10.0.10.1 -> 10.0.11.1:80"
          src: "10.0.10.1"
          dst: "10.0.11.1"
          protocol: "tcp"
          dst_port: 80
          bidirectional: false
          start_location: "@enter(fortigat_ansible[port4])"
    required: false
    type: list
    elements: dict
    default: []

author:
  - "Toi :)"
'''

EXAMPLES = r'''
- name: Valider quelques flux ICMP et TCP
  batfish_validate_reachability:
    host: 127.0.0.1
    port: 9996
    network: fortigate_lab
    snapshot: fortigate_snapshot_01
    snapshot_dir: /root/netops.fr/article/batfish/batfish/snapshot_fortigate
    flows:
      - name: "Ping 10.0.0.1 -> 10.0.0.2"
        src: "10.0.0.1"
        dst: "10.0.0.2"
        protocol: "icmp"
        bidirectional: true

      - name: "HTTP 10.0.10.1 -> 10.0.11.1:80 (unidirectionnel)"
        src: "10.0.10.1"
        dst: "10.0.11.1"
        protocol: "tcp"
        dst_port: 80
        bidirectional: false
        start_location: "fortigat_ansible[port4]"
  register: bf_reach

- name: Afficher les détails par flux
  debug:
    var: bf_reach.flows_details

- name: Echouer si un flux n'est pas atteignable
  fail:
    msg: "{{ bf_reach.tests_summary }}"
  when: not bf_reach.tests_ok
'''

RETURN = r'''
tests_ok:
  description: True si tous les flux sont atteignables (au moins un flow "successful" par flux).
  type: bool
  returned: always

tests_summary:
  description: >
    Liste de résumés (une entrée globale) :
      - name: "Reachability L3 des flux attendus"
        ok: bool
        message: string
  type: list
  elements: dict
  returned: always

flows_details:
  description: >
    Liste détaillée, une entrée par flux défini en entrée.
    Chaque entrée contient notamment :
      - name, src, dst, protocol, bidirectional, src_port, dst_port, start_location
      - forward: { ok, paths, error, flows }
      - backward: { ok, paths, error, flows } ou null si non bidirectionnel
    Le champ "flows" est une liste de dicts, chaque dict correspondant
    à une ligne de la réponse Batfish (toutes les colonnes sont renvoyées :
    Flow, Traces, Disposition, etc.), tous les champs étant des strings.
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
    from pybatfish.datamodel.flow import HeaderConstraints, PathConstraints
    HAS_PYBATFISH = True
except Exception:
    HAS_PYBATFISH = False


def _normalize_protocol(proto: str) -> str:
    """
    Normalise le protocole en icmp/tcp/udp, par défaut: icmp.
    """
    if not proto:
        return "icmp"
    p = proto.lower()
    if p in ("icmp", "tcp", "udp"):
        return p
    # fallback : on renvoie tel quel, Batfish lèvera éventuellement une erreur
    return p


def _extract_df_from_answer(ans):
    """
    Essaie de récupérer un DataFrame depuis l'Answer Batfish.
    Gère les cas où .frame() n'existe pas ou échoue.
    """
    df = None

    # 1) Essayer answer.frame()
    if hasattr(ans, "frame"):
        try:
            df = ans.frame()
        except Exception:
            df = None

    # Si on a un df exploitable, on le renvoie
    if df is not None:
        return df

    # 2) Fallback: essayer ans.rows (certaines versions)
    try:
        rows = ans.rows  # list[dict]
        import pandas as pd  # pybatfish dépend déjà de pandas
        return pd.DataFrame(rows)
    except Exception:
        pass

    # 3) Dernier recours: ans.dict() et chercher des "rows"
    try:
        d = ans.dict()
        # structure typique: {"answerElements": [{"rows": [...]} , ... ]}
        elems = d.get("answerElements") or []
        for el in elems:
            if "rows" in el:
                rows = el["rows"]
                import pandas as pd
                return pd.DataFrame(rows)
    except Exception:
        pass

    # Rien trouvé
    return None


def _run_one_direction(bf, src, dst, proto, src_port=None, dst_port=None, start_location=None):
    """
    Lance reachability() dans un sens, sans filtrer les actions (dispositions).
    Retourne un dict : {ok, paths, flows, error}
      - flows : liste de dicts, chaque dict = 1 row du DataFrame (toutes colonnes)
      - ok    : True si au moins une disposition "successful" est présente
    """
    headers_kwargs = {
        "srcIps": src,
        "dstIps": dst,
        "ipProtocols": [_normalize_protocol(proto)],
    }

    # Ports optionnels
    if src_port is not None:
        try:
            headers_kwargs["srcPorts"] = [int(src_port)]
        except (TypeError, ValueError):
            return dict(ok=False, paths=0, flows=[], error=f"src_port invalide: {src_port}")

    if dst_port is not None:
        try:
            headers_kwargs["dstPorts"] = [int(dst_port)]
        except (TypeError, ValueError):
            return dict(ok=False, paths=0, flows=[], error=f"dst_port invalide: {dst_port}")

    try:
        headers = HeaderConstraints(**headers_kwargs)

        q_kwargs = {"headers": headers}

        # PathConstraints si start_location fourni
        if start_location:
            try:
                pc = PathConstraints(startLocation=start_location)
                q_kwargs["pathConstraints"] = pc
            except Exception as e:
                return dict(
                    ok=False,
                    paths=0,
                    flows=[],
                    error=f"start_location invalide '{start_location}': {e}",
                )

        ans = bf.q.reachability(**q_kwargs).answer()
        df = _extract_df_from_answer(ans)

        if df is None or df.empty:
            # Aucun flow retourné, même en laissant toutes les dispositions
            return dict(
                ok=False,
                paths=0,
                flows=[],
                error="Aucun flow retourné par reachability() (aucune disposition).",
            )

        # *** IMPORTANT ***
        # On convertit TOUTES les colonnes en string (y compris Traces)
        # pour éviter d'avoir des objets non-sérialisables (Trace, etc.).
        df2 = df.copy()
        for col in df2.columns:
            try:
                df2[col] = df2[col].astype(str)
            except Exception:
                # Si cast impossible, on repasse à str() cellule par cellule
                df2[col] = df2[col].apply(lambda x: str(x))

        flows = df2.to_dict(orient="records")

        # Déterminer si au moins une disposition "success"
        success_dispositions = {
            "ACCEPTED",
            "DELIVERED_TO_SUBNET",
            "EXITS_NETWORK",
            "SUCCESS",
        }

        disp_col = None
        for candidate in ["Disposition", "FlowDisposition", "Flow_Disposition"]:
            if candidate in df2.columns:
                disp_col = candidate
                break

        ok = False
        if disp_col:
            for d in df2[disp_col]:
                if str(d).upper() in success_dispositions:
                    ok = True
                    break
        else:
            # Pas de colonne de disposition : on considère que la présence
            # de flows est un succès (à défaut de mieux)
            ok = True

        return dict(
            ok=ok,
            paths=len(df2),
            flows=flows,
            error=None,
        )

    except Exception as e:
        return dict(
            ok=False,
            paths=0,
            flows=[],
            error=f"Erreur reachability(): {e}",
        )


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
        flows_details=[],
        raw_batfish_errors=[],
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    if not HAS_PYBATFISH:
        module.fail_json(
            msg="Le module Python pybatfish est requis (pip install pybatfish).",
            **result
        )

    if module.check_mode:
        result['tests_ok'] = True
        result['tests_summary'].append(dict(
            name="Reachability L3 des flux attendus",
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
        bf = Session(host=host, port_v2=port, ssl=False)
        bf.set_network(network)
        bf.init_snapshot(snapshot_dir, name=snapshot, overwrite=True)
        bf.set_snapshot(snapshot)

        flows_details = []
        all_ok = True

        if not flows:
            # Pas de flux -> on considère OK, mais on le dit
            result["tests_ok"] = True
            result["flows_details"] = []
            result["tests_summary"].append(dict(
                name="Reachability L3 des flux attendus",
                ok=True,
                message="Aucun flux défini (tests ignorés)."
            ))
            module.exit_json(**result)

        for flow in flows:
            name = flow.get("name") or f"{flow.get('src')} -> {flow.get('dst')}"
            src = flow.get("src")
            dst = flow.get("dst")
            proto = _normalize_protocol(flow.get("protocol") or "icmp")
            bidir = bool(flow.get("bidirectional", False))
            src_port = flow.get("src_port")
            dst_port = flow.get("dst_port")
            start_location = flow.get("start_location")

            entry = dict(
                name=name,
                src=src,
                dst=dst,
                protocol=proto,
                bidirectional=bidir,
                src_port=src_port,
                dst_port=dst_port,
                start_location=start_location,
                forward=None,
                backward=None,
            )

            if not src or not dst:
                entry["forward"] = dict(
                    ok=False,
                    paths=0,
                    flows=[],
                    error="src ou dst manquant."
                )
                entry["backward"] = None
                all_ok = False
                flows_details.append(entry)
                continue

            # Sens aller (toujours testé)
            fwd = _run_one_direction(
                bf,
                src=src,
                dst=dst,
                proto=proto,
                src_port=src_port,
                dst_port=dst_port,
                start_location=start_location,
            )
            entry["forward"] = fwd
            if not fwd["ok"]:
                all_ok = False

            # Sens retour si demandé
            if bidir:
                bwd = _run_one_direction(
                    bf,
                    src=dst,
                    dst=src,
                    proto=proto,
                    src_port=dst_port,
                    dst_port=src_port,
                    start_location=start_location,
                )
                entry["backward"] = bwd
                if not bwd["ok"]:
                    all_ok = False
            else:
                entry["backward"] = None

            flows_details.append(entry)

        result["flows_details"] = flows_details
        result["tests_ok"] = all_ok

        ok_count = sum(
            1
            for f in flows_details
            if f["forward"]["ok"] and (
                not f["bidirectional"]
                or (f["backward"] and f["backward"]["ok"])
            )
        )
        total = len(flows_details)
        summary_msg = f"{ok_count}/{total} flux atteignables (au moins un flow 'successful' par flux)."

        result["tests_summary"].append(dict(
            name="Reachability L3 des flux attendus",
            ok=all_ok,
            message=summary_msg,
        ))

        module.exit_json(**result)

    except Exception as e:
        result["raw_batfish_errors"].append(str(e))
        module.fail_json(
            msg=f"Erreur lors de la validation Batfish (reachability): {e}",
            **result
        )


def main():
    run_module()


if __name__ == '__main__':
    main()

