
# Batfish Ansible Validation Modules

Modules Ansible personnalisés développés autour de Batfish pour industrialiser les validations réseau dans des pipelines NetOps / CI/CD.

Projet maintenu par :
https://github.com/netops-fr

---

# Objectif du projet

Ce dépôt fournit des modules Ansible permettant :

- d'interroger Batfish,
- de valider des routes,
- de tester des flux L3,
- de vérifier des ACL / filters,
- d'analyser des adjacences L3,
- d'intégrer Batfish dans GitLab CI/CD.

---

# Architecture du lab

VMware Workstation

VM Debian :
- Docker
- Batfish
- NetBox
- Ansible

VM EVE-NG :
- Cisco Nexus 9000v
- FortiGate VM

---

# Différence entre validate.py et validate_reachability.py

batfish_validate_reachability.py :
- module spécialisé
- tests de reachability uniquement
- paramètres directement dans le playbook

Exemple :

flows:
  - name: "Ping A vers B"
    src: "10.0.0.1"
    dst: "10.0.0.2"

---

batfish_validate.py :
- orchestrateur global
- charge un params.yml
- peut lancer plusieurs familles de tests

Exemple :

tests:
  reachability_flows:
    - name: "Ping A vers B"
      src: "10.0.0.1"
      dst: "10.0.0.2"

---

# validate.py utilise-t-il les autres libs ?

Actuellement, les modules semblent indépendants.

Architecture actuelle :

batfish_validate.py
= orchestrateur autonome

batfish_validate_routes.py
= module spécialisé

batfish_validate_reachability.py
= module spécialisé

---

# Installation

python3 -m venv ansible-env

source ansible-env/bin/activate

pip install ansible pybatfish pandas

---

# Désactiver le venv

deactivate

---

# GitHub

https://github.com/netops-fr

