# Batfish Ansible Modules — NETOPS.FR

Custom Ansible modules for Batfish network validation, CI/CD integration and NetOps workflows.

Repository: https://github.com/netops-fr/batfish_ansible  
Project: https://netops.fr

---

## 🚀 Project Overview

This repository contains a set of custom Ansible modules developed for integrating **Batfish** into practical NetOps workflows.

The goal of this project is to simplify:

- network validation
- reachability testing
- ACL / filter validation
- route verification
- L3 adjacency checks
- CI/CD integration
- pre-production network analysis
- infrastructure compliance checks

These modules were designed around practical NetOps use cases using:

- Batfish
- Ansible
- NetBox
- GitLab CI/CD
- Docker
- Cisco Nexus
- FortiGate
- EVE-NG labs

---

## 🧠 Why this project exists

Batfish is a powerful network analysis engine, but its historical Ansible integration is no longer ideal for modern environments.

The official `batfish/ansible` repository is archived and appears to rely on older pybatfish internals.  
During compatibility tests, the official module failed with errors such as:

```text
ModuleNotFoundError: No module named 'pybatfish.client._diagnostics'
```

This project provides a more practical and modern approach focused on:

- current Batfish deployments
- current pybatfish usage
- reusable custom Ansible modules
- CI/CD-friendly workflows
- simplified validation logic
- production-oriented NetOps pipelines

---

## 🏗️ Example Lab Architecture

Our validation lab currently uses:

- VMware Workstation
- Debian VM
  - NetBox container
  - Batfish container
  - Ansible environment
- EVE-NG VM
  - Cisco Nexus 9000v
  - FortiGate virtual firewall
- GitLab CI/CD
- Dynamic NetBox inventory

Example logical architecture:

```text
+-------------------------+
| VMware Workstation      |
|                         |
|  +-------------------+  |
|  | Debian VM          | |
|  | - Docker           | |
|  | - NetBox CT        | |
|  | - Batfish CT       | |
|  | - Ansible          | |
|  +---------+---------+  |
|            |            |
|  +---------+---------+  |
|  | EVE-NG VM          | |
|  | - Nexus 9000v      | |
|  | - FortiGate VM     | |
|  +-------------------+  |
+-------------------------+
```

---

## 🐟 How Batfish Works

Batfish runs as a server.

It does not connect directly to production devices.  
Instead, it analyzes **snapshots** built from exported network configurations.

Typical workflow:

```text
Network devices
   ↓
Configuration export
   ↓
snapshot/configs/
   ↓
Batfish server
   ↓
Ansible modules
   ↓
Validation result
```

Batfish exposes an API used by pybatfish and automation tools.

Typical ports:

- `9996`
- `9997`

Example Docker deployment:

```bash
docker run -d \
  --name batfish \
  -p 9997:9997 \
  -p 9996:9996 \
  batfish/allinone
```

---

## 📂 Snapshot Structure

Batfish expects snapshots to follow a specific structure.

Example:

```text
snapshot/
└── configs/
    ├── nexus01.cfg
    └── fortigate01.cfg
```

The configuration files must be compatible with Batfish-supported formats.

Useful documentation:

- https://batfish.readthedocs.io/en/latest/supported_devices.html
- https://batfish.readthedocs.io/en/latest/formats.html

---

## 📂 Repository Structure

Example project tree:

```text
.
├── ansible.cfg
├── group_vars
│   ├── all
│   │   ├── batfish.yml
│   │   ├── netbox.yml
│   │   └── params.yml
│   └── device_roles_switch
│       └── nexus.yml
├── inventories
│   └── netbox
│       └── netbox.yml
├── library
│   ├── batfish_questions.py
│   ├── batfish_validate_filterline.py
│   ├── batfish_validate_filters.py
│   ├── batfish_validate.py
│   ├── batfish_validate_reachability.py
│   └── batfish_validate_routes.py
├── pb01_netbox_get_sites.yml
├── pb02_test_inventaire_netbox.yml
├── pb03_nexus_interfaces.yml
├── pb04_batfish_questions.yml
├── pb05_batfish_validate.yml
├── sites.yml
└── webhooks
    └── app.py
```

---

## ⚙️ Ansible Project Layout

### `ansible.cfg`

Defines Ansible behavior for the project.

Example:

```ini
[defaults]
inventory = inventories/netbox/netbox.yml
library = ./library
host_key_checking = False
```

The key setting here is:

```ini
library = ./library
```

It tells Ansible to load custom modules from the local `library/` directory.

---

### `group_vars/`

Contains shared variables.

Example:

```text
group_vars/
├── all/
│   ├── batfish.yml
│   ├── netbox.yml
│   └── params.yml
└── device_roles_switch/
    └── nexus.yml
```

Typical usage:

- `batfish.yml`: Batfish host, port, network and snapshot variables
- `netbox.yml`: NetBox API endpoint and token reference
- `params.yml`: validation scenarios
- `device_roles_switch/nexus.yml`: Cisco Nexus connection variables

---

### `inventories/`

Contains Ansible inventory sources.

In this project, the inventory can be generated from NetBox:

```text
inventories/
└── netbox/
    └── netbox.yml
```

This allows Ansible to use NetBox as a source of truth.

---

### `library/`

Contains custom Ansible modules.

Each `.py` file inside this folder can be called as an Ansible module.

Example:

```yaml
- name: Validate routes with Batfish
  batfish_validate_routes:
    host: 127.0.0.1
    port: 9997
```

---

## 🧩 Module Architecture

This project currently contains two types of modules:

1. **specialized modules**
2. **a global validation module**

---

## 1. Specialized Modules

Specialized modules focus on one validation domain.

Examples:

| Module | Purpose |
|---|---|
| `batfish_validate_routes.py` | Validate routes and L3 adjacencies |
| `batfish_validate_reachability.py` | Validate L3 reachability flows |
| `batfish_validate_filters.py` | Validate ACL / filter behavior |
| `batfish_validate_filterline.py` | Detect unreachable / dead filter lines |
| `batfish_questions.py` | Run generic Batfish questions |

Specialized modules are useful when you want:

- a targeted test
- a simple playbook
- quick debugging
- a focused CI/CD job
- direct module parameters in the playbook

Example with `batfish_validate_reachability.py`:

```yaml
- name: Validate reachability
  batfish_validate_reachability:
    host: 127.0.0.1
    port: 9997
    network: lab_netops
    snapshot: snapshot_01
    snapshot_dir: ./snapshot
    flows:
      - name: "Ping A to B"
        src: "10.0.0.1"
        dst: "10.0.0.2"
        protocol: "icmp"
        bidirectional: true
```

In this case, the key is:

```yaml
flows:
```

because the module receives flows directly.

---

## 2. Global Module: `batfish_validate.py`

`batfish_validate.py` acts as a global validation entry point.

It loads a `params.yml` file and reads test definitions from it.

This module is more suitable for:

- industrialized workflows
- GitLab CI/CD pipelines
- centralized validation scenarios
- reusable test definitions
- separation between logic and test data

Example playbook:

```yaml
- name: Global Batfish validation
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:
    - name: Run global Batfish validation
      batfish_validate:
        host: 127.0.0.1
        port: 9997
        network: lab_netops
        snapshot: snapshot_01
        snapshot_dir: ./snapshot
        params_file: ./group_vars/all/params.yml
      register: bf_validate

    - name: Show validation summary
      debug:
        var: bf_validate.tests_summary

    - name: Fail if validation failed
      fail:
        msg: "{{ bf_validate.tests_summary }}"
      when: not bf_validate.tests_ok
```

---

## `params.yml` Structure

The global module expects test definitions under the `tests` key.

Example:

```yaml
tests:

  expected_static_routes:
    - node: "fortigat_ansible"
      network: "10.0.2.0/24"
      next_hop_ip: "10.0.0.2"

  expected_l3_edges:
    - node: "fortigat_ansible"
      iface: "port2"
      ip: "10.0.0.1"
      remote_node: "forti02"
      remote_iface: "port2"
      remote_ip: "10.0.0.2"

  reachability_flows:
    - name: "Ping Fortigate to Forti02"
      src: "10.0.0.1"
      dst: "10.0.0.2"
      protocol: "icmp"
      bidirectional: true

  filter_tests:
    flows:
      - name: "HTTP client to server"
        src: "10.0.10.1"
        dst: "10.0.11.1"
        protocol: "tcp"
        dst_port: 80
```

Important distinction:

```yaml
# Specialized reachability module
flows:
```

```yaml
# Global validate.py module
tests:
  reachability_flows:
```

---

## Does `batfish_validate.py` depend on the other modules?

At the current stage, `batfish_validate.py` appears to be **independent**.

It does not appear to import the specialized modules directly.

Current model:

```text
batfish_validate.py
= autonomous global validator

batfish_validate_routes.py
= specialized routes / L3 module

batfish_validate_reachability.py
= specialized reachability module

batfish_validate_filters.py
= specialized filter module
```

This means there may be some duplicated logic between the global module and the specialized modules.

A possible future improvement would be to refactor the project so that `batfish_validate.py` becomes a lightweight orchestrator that reuses common validation logic from shared Python utilities.

Possible future architecture:

```text
module_utils/
├── batfish_common.py
├── validators_routes.py
├── validators_reachability.py
└── validators_filters.py

library/
├── batfish_validate.py
├── batfish_validate_routes.py
├── batfish_validate_reachability.py
└── batfish_validate_filters.py
```

Benefits:

- less duplicated code
- easier maintenance
- consistent return structure
- easier transition to a real Ansible collection
- cleaner publication on Ansible Galaxy

---

## When to use which module?

### Use specialized modules when:

- you want a small targeted playbook
- you are debugging one validation type
- you want explicit parameters in the playbook
- you want to demonstrate one Batfish question
- you want simple examples for documentation

Example:

```yaml
batfish_validate_routes:
  expected_static_routes:
    - node: "router1"
      network: "10.0.0.0/24"
```

---

### Use `batfish_validate.py` when:

- you want a global CI/CD validation job
- you want to centralize scenarios in `params.yml`
- you want one playbook to run several validations
- you want a cleaner pipeline design
- you want test data separated from playbook logic

Example:

```yaml
batfish_validate:
  params_file: ./group_vars/all/params.yml
```

---

## 🔐 Secrets Management

Do not store secrets directly in YAML files.

Bad example:

```yaml
token: "nbt_xxxxxxxxx"
```

Recommended approach:

```bash
export NETBOX_TOKEN="nbt_xxxxxxxxx"
```

Then in Ansible:

```yaml
netbox_token: "{{ lookup('env', 'NETBOX_TOKEN') }}"
```

For GitLab CI/CD, store secrets in:

```text
Settings → CI/CD → Variables
```

---

## ⚙️ Installation

Clone repository:

```bash
git clone https://github.com/netops-fr/batfish_ansible.git
cd batfish_ansible
```

Create Python virtual environment:

```bash
python3 -m venv ansible-env
source ansible-env/bin/activate
```

Install dependencies:

```bash
pip install ansible pybatfish pandas
```

Deactivate virtual environment:

```bash
deactivate
```

---

## 📡 Example Snapshot Export

Example playbook used to export Cisco Nexus configuration files into a Batfish snapshot:

```yaml
---
- name: Export network configurations for Batfish
  hosts: switches
  gather_facts: false

  tasks:

    - name: Create snapshot/configs locally
      delegate_to: localhost
      file:
        path: "./snapshot/configs"
        state: directory
        mode: '0755'

    - name: Run show running-config all on Cisco NXOS devices
      cisco.nxos.nxos_command:
        commands:
          - "show running-config all"
      register: running_config

    - name: Save configuration into Batfish snapshot
      delegate_to: localhost
      copy:
        content: "{{ running_config.stdout[0] }}"
        dest: "./snapshot/configs/{{ inventory_hostname }}.cfg"
        mode: '0644'
```

---

## 🔎 Example Route Validation

```yaml
---
- name: Validate routes and L3 adjacencies with Batfish
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:

    - name: Validate static routes and L3 edges
      batfish_validate_routes:
        host: 127.0.0.1
        port: 9997
        network: lab_netops
        snapshot: snapshot_01
        snapshot_dir: ./snapshot

        check_no_default_route: true

        expected_static_routes:
          - node: "fortigat_ansible"
            network: "10.0.2.0/24"
            next_hop_ip: "10.0.0.2"

        expected_l3_edges:
          - node: "fortigat_ansible"
            iface: "port2"
            ip: "10.0.0.1"
            remote_node: "forti02"
            remote_iface: "port2"
            remote_ip: "10.0.0.2"

      register: bf_routes

    - name: Show summary
      debug:
        var: bf_routes.tests_summary

    - name: Fail if route validation failed
      fail:
        msg: "{{ bf_routes.tests_summary }}"
      when: not bf_routes.tests_ok
```

---

## 🔎 Example Reachability Validation

```yaml
---
- name: Validate reachability with Batfish
  hosts: localhost
  connection: local
  gather_facts: false

  tasks:

    - name: Validate expected flows
      batfish_validate_reachability:
        host: 127.0.0.1
        port: 9997
        network: lab_netops
        snapshot: snapshot_01
        snapshot_dir: ./snapshot

        flows:
          - name: "Ping Fortigate to Forti02"
            src: "10.0.0.1"
            dst: "10.0.0.2"
            protocol: "icmp"
            bidirectional: true

          - name: "HTTP client to server"
            src: "10.0.10.1"
            dst: "10.0.11.1"
            protocol: "tcp"
            dst_port: 80
            bidirectional: false

      register: bf_reachability

    - name: Show summary
      debug:
        var: bf_reachability.tests_summary

    - name: Fail if reachability validation failed
      fail:
        msg: "{{ bf_reachability.tests_summary }}"
      when: not bf_reachability.tests_ok
```

---

## 🔄 Example NetOps Workflow

```text
NetBox
   ↓
Dynamic Inventory
   ↓
Ansible
   ↓
Configuration Export
   ↓
Batfish Snapshot
   ↓
Batfish Validation
   ↓
GitLab CI/CD
   ↓
Report / Pass / Fail
```

---

## 🧰 Technologies Used

- Python
- Ansible
- Batfish
- pybatfish
- Docker
- NetBox
- GitLab CI/CD
- Cisco NXOS
- FortiGate
- EVE-NG

---

## ⚠️ Notes

- Batfish requires vendor configurations in supported formats.
- Snapshots must follow Batfish expected directory structure.
- The official Batfish Ansible integration is archived and may not work with current pybatfish versions.
- This repository is experimental and continuously evolving.
- The current module design separates specialized modules from the global validator.
- A future refactor may introduce shared module utilities.

---

## 📚 Useful Resources

Official Batfish Documentation:

https://batfish.readthedocs.io/

Supported devices:

https://batfish.readthedocs.io/en/latest/supported_devices.html

Supported formats:

https://batfish.readthedocs.io/en/latest/formats.html

NETOPS.FR GitHub:

https://github.com/netops-fr

NETOPS.FR website:

https://netops.fr

---

## 📜 License

MIT License

---

## ⭐ Support the Project

If this repository helps you:

- star the repository
- share it
- contribute improvements
- open issues
- publish validation scenarios

NetOps automation and continuous validation deserve more open tooling.

