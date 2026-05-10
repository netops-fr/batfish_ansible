from flask import Flask, request
from datetime import datetime
import json
import subprocess

app = Flask(__name__)


def pretty_title(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def pretty_json(label, data):
    print(f"\n--- {label} ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def print_vlan_list(title, vlans):
    print(f"\n{title}:")
    if not vlans:
        print("  aucun")
        return

    for vlan in vlans:
        if isinstance(vlan, dict):
            print(
                f"  - VID={vlan.get('vid')} "
                f"name={vlan.get('name')} "
                f"id={vlan.get('id')}"
            )
        else:
            print(f"  - {vlan}")


@app.route("/webhook", methods=["POST"])
def webhook():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    headers = dict(request.headers)
    raw_body = request.get_data(as_text=True)
    data = request.get_json(silent=True)

    pretty_title(f"WEBHOOK REÇU - {now}")

    print(f"\nSource IP : {request.remote_addr}")
    print(f"Method    : {request.method}")
    print(f"Path      : {request.path}")

    pretty_json("Headers", headers)

    print("\n--- Raw body ---")
    print(raw_body if raw_body else "<body vide>")

    if data is None:
        print("\n--- JSON parsed ---")
        print("Aucun JSON valide reçu")
        return "OK\n", 200

    pretty_json("JSON parsed", data)

    event = data.get("event")
    object_type = data.get("object_type")

    print("\n--- Résumé ---")
    print(f"Event       : {event}")
    print(f"Object type : {object_type}")

    if object_type == "dcim.interface":
        print(f"Device       : {data.get('device')}")
        print(f"Interface    : {data.get('interface')}")
        print(f"Mode         : {data.get('mode')}")
        print(f"Untagged VID : {data.get('untagged_vlan_vid')}")
        print(f"Untagged     : {data.get('untagged_vlan_name')}")

        print_vlan_list(
            "Tagged VLANs",
            data.get("tagged_vlans", [])
        )

        print(f"\nTagged VIDs  : {data.get('tagged_vlan_vids', [])}")

        print("\n--- Changements bruts ---")
        print(f"Old untagged object ID : {data.get('old_untagged_vlan_object_id')}")
        print(f"New untagged object ID : {data.get('new_untagged_vlan_object_id')}")
        print(f"Old tagged object IDs  : {data.get('old_tagged_vlan_object_ids')}")
        print(f"New tagged object IDs  : {data.get('new_tagged_vlan_object_ids')}")

    elif object_type == "dcim.device":
        print(f"Device      : {data.get('name')}")
        print(f"Status      : {data.get('status')}")
        print(f"Old status  : {data.get('old_status')}")
        print(f"New status  : {data.get('new_status')}")

    print("=" * 80 + "\n")

    extra_vars = {
        "target_device": data.get("device"),
        "webhook_event": data.get("event"),
        "webhook_object_type": data.get("object_type"),
        "webhook_device": data.get("device"),
        "webhook_interface": data.get("interface"),
        "webhook_mode": data.get("mode"),
        "webhook_untagged_vlan_vid": data.get("untagged_vlan_vid"),
        "webhook_tagged_vlan_vids": data.get("tagged_vlan_vids", []),
    }

    cmd = [
        "ansible-playbook",
        "-i", "../inventories/netbox/netbox.yml",
        "../pb03_nexus_interfaces.yml",
        "--extra-vars", json.dumps(extra_vars),
    ]

    print("\n--- Lancement Ansible ---")
    print(" ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    print("\n--- Ansible stdout ---")
    print(result.stdout)

    print("\n--- Ansible stderr ---")
    print(result.stderr)

    print(f"\nCode retour Ansible : {result.returncode}")

    return "OK\n", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
