# batfish_ansible
# Batfish Ansible Modules — NETOPS.FR

Custom Ansible modules for Batfish network validation, CI/CD integration and NetOps workflows.

---

# 🚀 Project Overview

This repository contains a set of custom Ansible modules developed for integrating Batfish into real-world NetOps workflows.

The goal of this project is to simplify:

- network validation
- reachability testing
- ACL / filter validation
- route verification
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

# 🧠 Why this project exists

The official Batfish Ansible collection appears outdated and incompatible with recent versions of pybatfish.

This repository provides an alternative approach focused on:

- modern Batfish deployments
- reusable Ansible modules
- CI/CD-friendly workflows
- simplified validation logic
- production-oriented NetOps pipelines

---

# 🏗️ Example Lab Architecture

Our validation lab currently uses:

- VMware Workstation
- Debian VM
  - NetBox container
  - Batfish container
- EVE-NG VM
  - Cisco Nexus 9000v
  - FortiGate virtual firewall
- GitLab CI/CD
- Dynamic NetBox inventory

---

# 📂 Repository Structure

```text
.
├── ansible.cfg
├── group_vars
├── inventories
├── library
├── pb01_netbox_get_sites.yml
├── pb02_test_inventaire_netbox.yml
├── pb03_nexus_interfaces.yml
├── pb04_batfish_questions.yml
├── pb05_batfish_validate.yml
└── webhooks
```

---

# ⚙️ Installation

## Clone repository

```bash
git clone https://github.com/netops-fr/batfish_ansible.git
cd batfish_ansible
```

## Create Python virtual environment

```bash
python3 -m venv ansible-env
source ansible-env/bin/activate
```

## Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🐳 Batfish Deployment

Example Docker deployment:

```bash
docker run -d \
  --name batfish \
  -p 9997:9997 \
  -p 9996:9996 \
  batfish/allinone
```

---

# 🔐 Environment Variables

Do NOT store secrets directly inside YAML files.

Recommended approach:

```bash
export NETBOX_TOKEN="nbt_xxxxxxxxx"
```

Example:

```yaml
netbox_token: "{{ lookup('env', 'NETBOX_TOKEN') }}"
```

---

# 📡 Example Snapshot Export

```yaml
- name: Export configurations for Batfish
  hosts: switches
  gather_facts: false

  tasks:

    - name: Create snapshot directory
      delegate_to: localhost
      file:
        path: "./snapshot/configs"
        state: directory

    - name: Run show running-config all
      cisco.nxos.nxos_command:
        commands:
          - "show running-config all"
      register: running_config

    - name: Save configuration
      delegate_to: localhost
      copy:
        content: "{{ running_config.stdout[0] }}"
        dest: "./snapshot/configs/{{ inventory_hostname }}.cfg"
```

---

# 🔎 Example Validation

```yaml
- name: Validation reachability Batfish
  hosts: localhost
  gather_facts: false

  tasks:

    - name: Reachability validation
      batfish_validate_reachability:
        bf_host: "{{ bf_host }}"
        bf_network: "{{ bf_network }}"
        bf_snapshot: "{{ bf_snapshot }}"
```

---

# 🧪 Current Modules

- batfish_questions.py
- batfish_validate.py
- batfish_validate_reachability.py
- batfish_validate_routes.py
- batfish_validate_filters.py
- batfish_validate_filterline.py

---

# 🔄 Example NetOps Workflow

```text
NetBox
   ↓
Dynamic Inventory
   ↓
Ansible
   ↓
Snapshot Export
   ↓
Batfish Validation
   ↓
GitLab CI/CD
```

---

# 🧰 Technologies Used

- Python
- Ansible
- Batfish
- Docker
- NetBox
- GitLab CI/CD
- Cisco NXOS
- FortiGate
- EVE-NG

---

# 📚 Useful Resources

- https://batfish.readthedocs.io/
- https://batfish.readthedocs.io/en/latest/supported_devices.html
- https://batfish.readthedocs.io/en/latest/formats.html

---

# 🌍 NETOPS.FR

- https://netops.fr
- https://github.com/netops-fr

---

# 📜 License

MIT License

