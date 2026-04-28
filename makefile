# ============================================================
# 📌 Variables globales
# ============================================================
PROJECT_PATH_APP := $(shell pwd)/core
PROJECT_PATH := $(shell pwd)
LOGS_FILE := $(shell pwd)/log/app.log


# Variables pour gestion liens symboliques
FROM ?= /path/to/module.py     # Source du module (fichier ou dossier)
TO ?=  $(shell pwd)/backgroundtask           # Dossier destination
NAME ?= module.py              # Nom du lien symbolique

# Variables pour gestion plugins
PLUGIN_NAME ?= myplugin
AUTHOR ?= traoreera
PLUGIN_REPO ?= http://github.com/$(AUTHOR)/$(PLUGIN_NAME).git
PLUGIN_DIR := plugins/$(PLUGIN_NAME)


# ============================================================
# 📚 Commande HELP - Affiche toutes les commandes disponibles
# ============================================================
help: ## Afficher la liste des commandes disponibles et leur usage
	@echo "📚 Liste des commandes disponibles :"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ============================================================
# 🤖 Automatisation qualité / sécurité / docs
# ============================================================

REPORT_DIR ?= $(CURDIR)/reports
STRICT ?= 0
AUTOMATE_CMD ?= all

autobuild-ast: ## Afficher l'environnement Python détecté pour l'automatisation
	@echo "[INFO] Mode automation: poetry run"
	cd xcore/kernel/security/ && poetry run python setup.py build_ext --inplace

auto-setup: ## Installer les dépendances (poetry --with dev,docs)
	@echo "[INFO] Installation dépendances (dev + docs)"
	@poetry install --with dev,docs || { \
		if [ "$(STRICT)" = "1" ]; then \
			echo "[ERR ] Echec auto-setup"; exit 1; \
		else \
			echo "[WARN] Echec ignoré (STRICT=0): auto-setup"; \
		fi; \
	}

auto-tests: ## Lancer les tests unitaires
	@echo "[INFO] Tests unitaires (pytest)"
	@poetry run pytest -q || { \
		if [ "$(STRICT)" = "1" ]; then \
			echo "[ERR ] Echec tests unitaires"; exit 1; \
		else \
			echo "[WARN] Echec ignoré (STRICT=0): tests unitaires"; \
		fi; \
	}

auto-security: ## Audit sécurité (Bandit) avec rapports dans REPORT_DIR
	@mkdir -p "$(REPORT_DIR)"
	@echo "[INFO] Audit sécurité Bandit (JSON)"
	@poetry run bandit -r "$(CURDIR)/xcore" -f json -o "$(REPORT_DIR)/security-bandit.json" 2> "$(REPORT_DIR)/security-bandit.stderr.log" || { \
		if grep -q "ast' has no attribute 'Num'" "$(REPORT_DIR)/security-bandit.stderr.log"; then \
			echo "[WARN] Bandit a crashé (incompatibilité ast.Num)"; \
			echo '{"status":"failed","reason":"Bandit internal error: ast.Num incompatibility","tool":"bandit"}' > "$(REPORT_DIR)/security-bandit.json"; \
			echo "Bandit failed due to internal compatibility error (ast.Num)." > "$(REPORT_DIR)/security-bandit.txt"; \
			exit 0; \
		fi; \
		if [ "$(STRICT)" = "1" ]; then \
			echo "[ERR ] Echec audit Bandit JSON"; exit 1; \
		else \
			echo "[WARN] Echec ignoré (STRICT=0): audit Bandit JSON"; \
		fi; \
	}
	@echo "[INFO] Audit sécurité Bandit (TXT)"
	@poetry run bandit -r "$(CURDIR)/xcore" -f txt -o "$(REPORT_DIR)/security-bandit.txt" 2>> "$(REPORT_DIR)/security-bandit.stderr.log" || { \
		if [ "$(STRICT)" = "1" ]; then \
			echo "[ERR ] Echec audit Bandit TXT"; exit 1; \
		else \
			echo "[WARN] Echec ignoré (STRICT=0): audit Bandit TXT"; \
		fi; \
	}
	@echo "[INFO] Rapports sécurité:"
	@echo "[INFO] - $(REPORT_DIR)/security-bandit.json"
	@echo "[INFO] - $(REPORT_DIR)/security-bandit.txt"
	@echo "[INFO] - $(REPORT_DIR)/security-bandit.stderr.log"

auto-docs: ## Build docs Sphinx HTML
	@mkdir -p "$(CURDIR)/docs/_build/html"
	@echo "[INFO] Build docs Sphinx"
	@poetry run sphinx-build -b html "$(CURDIR)/docs" "$(CURDIR)/docs/_build/html" || { \
		if [ "$(STRICT)" = "1" ]; then \
			echo "[ERR ] Echec build docs"; exit 1; \
		else \
			echo "[WARN] Echec ignoré (STRICT=0): build docs"; \
		fi; \
	}
	@echo "[INFO] Documentation HTML: $(CURDIR)/docs/_build/html/index.html"

auto-all: auto-setup auto-tests auto-security auto-docs ## Exécuter toute la chaîne auto

automate: ## Exécuter l'automatisation full makefile (AUTOMATE_CMD=all|env|setup|tests|security|docs)
	@case "$(AUTOMATE_CMD)" in \
		all) $(MAKE) auto-all ;; \
		env) $(MAKE) auto-env ;; \
		setup) $(MAKE) auto-setup ;; \
		tests) $(MAKE) auto-tests ;; \
		security) $(MAKE) auto-security ;; \
		docs) $(MAKE) auto-docs ;; \
		*) echo "❌ AUTOMATE_CMD invalide: $(AUTOMATE_CMD)"; exit 2 ;; \
	esac

# ============================================================
# 🔧 Gestion des plugins (git + liens symboliques)
# ============================================================

add-plugin: ## Ajouter ou mettre à jour un plugin git et lier les tâches dans backgroundtask
	@if [ -z "$(PLUGIN_NAME)" ]; then \
		echo "❌ Erreur : veuillez fournir PLUGIN_NAME"; \
		echo "   Exemple : make add-plugin PLUGIN_NAME=presence"; \
		exit 1; \
	fi
	@if [ -z "$(PLUGIN_REPO)" ]; then \
		echo "⚠️ PLUGIN_REPO non défini, utilisation par défaut git@github.com:tonrepo/$(PLUGIN_NAME).git"; \
		export PLUGIN_REPO=git@github.com:tonrepo/$(PLUGIN_NAME).git; \
	fi
	@if [ ! -d "$(PLUGIN_DIR)" ]; then \
		echo "📥 Clonage du plugin $(PLUGIN_NAME) depuis $(PLUGIN_REPO)..."; \
		git clone "$(PLUGIN_REPO)" "$(PLUGIN_DIR)" || { echo "❌ Échec du clonage"; exit 1; }; \
	else \
		echo "⬆️ Mise à jour du plugin $(PLUGIN_NAME)..."; \
		cd "$(PLUGIN_DIR)" && git pull || { echo "❌ Échec de la mise à jour"; exit 1; }; \
	fi

rm-plugin: ## Suprime un plugin
	@if [ -z "$(PLUGIN_NAME)" ]; then \
		echo "❌ Erreur : veuillez fournir PLUGIN_NAME"; \
		echo "   Exemple : make rm-plugin PLUGIN_NAME=presence"; \
		exit 1; \
	fi
	@if [ ! -d "$(PLUGIN_DIR)" ]; then \
		echo "⚠️  Plugin $(PLUGIN_NAME) introuvable"; \
	else \
		echo "🗑 Suppression du plugin $(PLUGIN_NAME)..."; \
		rm -rf "$(PLUGIN_DIR)" || { echo "❌ Échec de la suppression"; exit 1; }; \
		echo "✅ Plugin $(PLUGIN_NAME) supprimé"; \
	fi

# ============================================================
# 🔗 Création / suppression de liens symboliques
# ============================================================

link: ## Créer un lien symbolique (usage: make link FROM=source TO=destination NAME=nom_lien)
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ] || [ -z "$(NAME)" ]; then \
		echo "❌ Erreur : il faut fournir FROM, TO et NAME"; \
		echo "   Exemple : make link FROM=./plugins/presence/task/presence_task.py TO=./backgroundtask NAME=presence.py"; \
		exit 1; \
	fi
	@if [ ! -f "$(FROM)" ]; then \
		echo "❌ Fichier source '$(FROM)' introuvable."; \
		exit 1; \
	fi
	@echo "🔗 Création du lien symbolique $(TO)/$(NAME) vers $(FROM)..."
	@if [ ! -d "$(TO)" ]; then \
		echo "📂 Création du dossier $(TO)"; \
		mkdir -p "$(TO)"; \
	fi

	@ln -sf "$(PROJECT_PATH)/$(FROM)" "$(TO)/$(NAME)"
	@echo "✅ Liens créés :"
	@echo "   $(TO)/$(NAME)"

unlink: ## Supprimer un lien symbolique (usage: make unlink TO=dossier NAME=nom_fichier)
	@echo "🗑 Suppression du lien symbolique $(TO)/$(NAME)..."
	@if [ -L "$(TO)/$(NAME)" ]; then \
		rm "$(TO)/$(NAME)"; \
		echo "✅ Lien supprimé : $(TO)/$(NAME)"; \
	else \
		echo "⚠️ Aucun lien trouvé pour $(TO)/$(NAME)"; \
	fi

# ============================================================
# 🧹 Nettoyage fichiers Python compilés
# ============================================================

clean: ## Supprimer __pycache__ et fichiers *.pyc, *.pyo
	@clear
	@echo "🧹 Nettoyage des fichiers inutiles..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f \( -name "*.backup" -o -name "*.backup" \) -exec rm -f {} +
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -exec rm -f {} +

# ============================================================
# 📦 Installation & initialisation projet
# ============================================================

install: ## Installer les dépendances Python via Poetry
	@poetry lock
	@poetry install

init: ## Initialiser le projet (permissions scripts + install + démarrage dev)
	@chmod +x ./script/uninstall.sh
	@chmod +x ./script/install.sh
	@chmod +x ./script/cmd.sh
	@chmod +x ./script/repaire_ng.sh
	@chmod +x ./script/restart_poetry.sh
	$(MAKE) install
	$(MAKE) run-dev

# ============================================================
# 🚀 Lancement de l'application
# ============================================================

dev: ## Lancer en mode développement (reload automatique)
	@echo "🚀 Lancement en mode développement..."
	@$(MAKE) clean
	@poetry run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

st: ## Lancer en mode production / statique (sans reload)
	@echo "🚀 Lancement en mode statique..."
	@$(MAKE) clean
	@poetry run python -m uvicorn main:app --host 0.0.0.0 --port 8000

testing: ## Installer pip sans cache (debug)
	@echo "📦 Installation pip sans cache..."
	@poetry run python -m uvicorn test:app --reload --host 0.0.0.0 --port 8082

# ============================================================
# 📦 Déploiement & gestion serveur
# ============================================================

deploy: ## Déployer l'application (script externe)
	@./script/install.sh

remove-app: ## Supprimer l'application (script externe)
	@./script/uninstall.sh

repaire-ng: ## Réparer la configuration Nginx
	@./script/repaire_ng.sh

start: ## Démarrer le serveur (script externe)
	@./script/cmd.sh start

stop: ## Arrêter le serveur (script externe)
	@./script/cmd.sh stop

restart: ## Redémarrer le serveur (script externe)
	@./script/cmd.sh restart

status: ## Vérifier le statut du serveur (script externe)
	@./script/cmd.sh status

poetry-ri: ## Redémarrer Poetry (script externe)
	@./script/restart_poetry.sh


# ============================================================
# 📌 Cibles "PHONY" - éviter conflits avec fichiers du même nom
# ============================================================

.PHONY: help automate auto-all auto-env auto-setup auto-tests auto-security auto-docs add-plugin link unlink clean install init run-dev run-st pip-Noa deploy remove-app repaire-ng start stop restart status poetry-ri pre-commit logs logs-live logs-debug logs-info logs-warning logs-error logs-critical logs-auth logs-db logs-api logs-plugins logs-tasks logs-email logs-clean logs-stats logs-search logs-today logs-last-hour logs-test logs-demo

# ============================================================
# 📊 Commandes de gestion des logs
# ============================================================

logs: ## Afficher tous les logs du fichier $(LOGS_FILE)
	@echo "📋 Affichage de tous les logs..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		tail -100 $(LOGS_FILE); \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-live: ## Afficher les logs en temps réel (tail -f)
	@echo "🔴 Logs en temps réel (Ctrl+C pour arrêter)..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		tail -f $(LOGS_FILE); \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-debug: ## Filtrer et afficher seulement les logs DEBUG
	@echo "🔍 Logs DEBUG..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "DEBUG" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-info: ## Filtrer et afficher seulement les logs INFO
	@echo "ℹ️  Logs INFO..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "INFO" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-warning: ## Filtrer et afficher seulement les logs WARNING
	@echo "⚠️  Logs WARNING..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "WARNING" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-error: ## Filtrer et afficher seulement les logs ERROR
	@echo "❌ Logs ERROR..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "ERROR" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-critical: ## Filtrer et afficher seulement les logs CRITICAL
	@echo "🚨 Logs CRITICAL..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "CRITICAL" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-auth: ## Filtrer les logs liés à l'authentification
	@echo "🔐 Logs d'authentification..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(auth|login|token|otp|session)" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-db: ## Filtrer les logs liés à la base de données
	@echo "🗃️  Logs de base de données..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(database|session|CRUD|commit|rollback)" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-api: ## Filtrer les logs liés aux routes/API
	@echo "🛣️  Logs des routes API..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(routes|router|API|endpoint)" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-plugins: ## Filtrer les logs liés aux plugins
	@echo "🔌 Logs des plugins..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(plugin|Plugin)" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-tasks: ## Filtrer les logs liés aux tâches
	@echo "📋 Logs des tâches..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(task|TaskManager|thread|service)" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-email: ## Filtrer les logs liés aux emails
	@echo "📧 Logs des emails..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(email|smtp|mail)" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-clean: ## Nettoyer/vider le fichier de logs
	@echo "🧹 Nettoyage du fichier de logs..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		echo "📁 Sauvegarde de $(LOGS_FILE) vers $(LOGS_FILE).old"; \
		cp $(LOGS_FILE) $(LOGS_FILE).old; \
		echo "" > $(LOGS_FILE); \
		echo "✅ Fichier $(LOGS_FILE) nettoyé (sauvegarde dans $(LOGS_FILE).old)"; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-stats: ## Afficher les statistiques des logs
	@echo "📊 Statistiques des logs..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		echo "📋 Nombre total de lignes: $$(wc -l < $(LOGS_FILE))"; \
		echo "🔍 DEBUG: $$(grep -c 'DEBUG' $(LOGS_FILE) || echo 0)"; \
		echo "ℹ️  INFO: $$(grep -c 'INFO' $(LOGS_FILE) || echo 0)"; \
		echo "⚠️  WARNING: $$(grep -c 'WARNING' $(LOGS_FILE) || echo 0)"; \
		echo "❌ ERROR: $$(grep -c 'ERROR' $(LOGS_FILE) || echo 0)"; \
		echo "🚨 CRITICAL: $$(grep -c 'CRITICAL' $(LOGS_FILE) || echo 0)"; \
		echo ""; \
		echo "🕐 Dernière entrée: $$(tail -1 $(LOGS_FILE) | cut -d' ' -f1-2 || echo 'N/A')"; \
		echo "📏 Taille du fichier: $$(du -h $(LOGS_FILE) | cut -f1)"; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-search: ## Rechercher dans les logs (usage: make logs-search TERM="texte_recherche")
	@if [ -z "$(TERM)" ]; then \
		echo "❌ Erreur : veuillez fournir un terme de recherche"; \
		echo "   Exemple : make logs-search TERM='utilisateur'"; \
		exit 1; \
	fi
	@echo "🔍 Recherche de '$(TERM)' dans les logs..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -i "$(TERM)" $(LOGS_FILE) | tail -30; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-today: ## Afficher les logs d'aujourd'hui
	@echo "📅 Logs d'aujourd'hui..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "$$(date '+%Y-%m-%d')" $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-last-hour: ## Afficher les logs de la dernière heure
	@echo "🕐 Logs de la dernière heure..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		awk -v hour="$$(date -d '1 hour ago' '+%Y-%m-%d %H')" '$$0 >= hour' $(LOGS_FILE) | tail -50; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi


logs-test: ## Générer des logs de test pour démonstration
	@echo "🧪 Génération de logs de test..."
	@python3 generate_test_logs.py

logs-demo: ## Démonstration complète du système de logs
	@echo "🎭 Démonstration complète du système de logging..."
	@echo ""
	@$(MAKE) logs-test
	@echo ""
	@echo "📊 Statistiques:"
	@$(MAKE) logs-stats
	@echo ""
	@echo "❌ Erreurs détectées:"
	@$(MAKE) logs-error
	@echo ""
	@echo "⚠️  Avertissements:"
	@$(MAKE) logs-warning
	@echo ""
	@echo "🔐 Logs d'authentification:"
	@$(MAKE) logs-auth

# ============================================================
# 🔄 Commandes combinées pour workflows avancés
# ============================================================

logs-errors-and-warnings: ## Afficher les erreurs ET les warnings ensemble
	@echo "🚨 Analyse complète : ERREURS + AVERTISSEMENTS"
	@echo "=================================================="
	@echo ""
	@echo "❌ ERREURS RÉCENTES:"
	@echo "-------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "ERROR" $(LOGS_FILE) | tail -20; \
	fi
	@echo ""
	@echo "⚠️  AVERTISSEMENTS RÉCENTS:"
	@echo "-------------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "WARNING" $(LOGS_FILE) | tail -20; \
	fi
	@echo ""
	@echo "📊 RÉSUMÉ:"
	@if [ -f "$(LOGS_FILE)" ]; then \
		echo "❌ Total erreurs: $$(grep -c 'ERROR' $(LOGS_FILE) || echo 0)"; \
		echo "⚠️  Total warnings: $$(grep -c 'WARNING' $(LOGS_FILE) || echo 0)"; \
	fi

logs-security-audit: ## Audit de sécurité complet (auth + erreurs + warnings)
	@echo "🛡️  AUDIT DE SÉCURITÉ COMPLET"
	@echo "=============================="
	@echo ""
	@echo "🔐 AUTHENTIFICATION:"
	@echo "-------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(auth|login|token|otp|session)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "❌ ERREURS DE SÉCURITÉ:"
	@echo "----------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ERROR.*auth|ERROR.*login|ERROR.*token)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "⚠️  TENTATIVES SUSPECTES:"
	@echo "------------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(WARNING.*auth|WARNING.*login|Échec|échec|Invalid|invalid)" $(LOGS_FILE) | tail -10; \
	fi

logs-performance-check: ## Vérification des performances (warnings + tasks + timing)
	@echo "⚡ VÉRIFICATION DES PERFORMANCES"
	@echo "==============================="
	@echo ""
	@echo "⚠️  ALERTES DE PERFORMANCE:"
	@echo "--------------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(lente|slow|timeout|performance|CPU|mémoire|memory)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "📋 ÉTAT DES TÂCHES:"
	@echo "------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(task|TaskManager|thread|service)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "⏱️  TEMPS D'EXÉCUTION:"
	@echo "---------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(exécuté en|ms|secondes)" $(LOGS_FILE) | tail -10; \
	fi

logs-startup-analysis: ## Analyse complète du démarrage de l'application
	@echo "🚀 ANALYSE DU DÉMARRAGE"
	@echo "======================"
	@echo ""
	@echo "🔧 INITIALISATION:"
	@echo "-----------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Démarrage|initialisé|chargé|startup)" $(LOGS_FILE) | tail -20; \
	fi
	@echo ""
	@echo "❌ ERREURS AU DÉMARRAGE:"
	@echo "-----------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ERROR.*init|ERROR.*startup|ERROR.*Démarrage)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "🔌 CHARGEMENT DES PLUGINS:"
	@echo "-------------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Plugin.*chargé|plugin.*initialisé)" $(LOGS_FILE) | tail -10; \
	fi

logs-user-activity: ## Activité des utilisateurs (connexions, actions, erreurs)
	@echo "👥 ACTIVITÉ DES UTILISATEURS"
	@echo "==========================="
	@echo ""
	@echo "🔐 CONNEXIONS:"
	@echo "-------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Tentative de connexion|Connexion réussie|login)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "🚪 DÉCONNEXIONS:"
	@echo "---------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Déconnexion|logout)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "📝 INSCRIPTIONS:"
	@echo "---------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Inscription|register)" $(LOGS_FILE) | tail -10; \
	fi

logs-api-monitoring: ## Monitoring des API (routes + erreurs + performance)
	@echo "🛣️  MONITORING DES API"
	@echo "====================="
	@echo ""
	@echo "📊 ACCÈS AUX ROUTES:"
	@echo "-------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(GET|POST|DELETE|PUT)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "❌ ERREURS D'API:"
	@echo "----------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ERROR.*route|ERROR.*API|ERROR.*endpoint)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "⏱️  PERFORMANCE DES ROUTES:"
	@echo "--------------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ms|temps.*exécution)" $(LOGS_FILE) | tail -10; \
	fi

logs-database-health: ## Santé de la base de données (connexions + erreurs + transactions)
	@echo "🗃️  SANTÉ DE LA BASE DE DONNÉES"
	@echo "==============================="
	@echo ""
	@echo "🔗 CONNEXIONS:"
	@echo "-------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(database.*établie|Session.*créée|DB)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "💾 TRANSACTIONS:"
	@echo "---------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(commit|rollback|transaction)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "❌ ERREURS DE BASE:"
	@echo "------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ERROR.*database|ERROR.*DB|ERROR.*SQL)" $(LOGS_FILE) | tail -10; \
	fi

logs-plugins-status: ## État complet des plugins (chargement + erreurs + activité)
	@echo "🔌 ÉTAT COMPLET DES PLUGINS"
	@echo "=========================="
	@echo ""
	@echo "🔧 CHARGEMENT DES PLUGINS:"
	@echo "-------------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Plugin.*chargé|plugin.*initialisé|Manager.*plugin)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "⚡ ACTIVITÉ DES PLUGINS:"
	@echo "----------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Plugin|plugin)" $(LOGS_FILE) | grep -E "(ajouté|supprimé|créé)" | tail -10; \
	fi
	@echo ""
	@echo "❌ ERREURS DE PLUGINS:"
	@echo "---------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ERROR.*plugin|ERROR.*Plugin)" $(LOGS_FILE) | tail -10; \
	fi

logs-email-monitoring: ## Monitoring complet des emails (envois + erreurs + SMTP)
	@echo "📧 MONITORING DES EMAILS"
	@echo "======================="
	@echo ""
	@echo "📮 ENVOIS D'EMAILS:"
	@echo "------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(Envoi d'email|email.*envoyé|email.*succès)" $(LOGS_FILE) | tail -15; \
	fi
	@echo ""
	@echo "🔧 CONNEXIONS SMTP:"
	@echo "------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(SMTP|smtp)" $(LOGS_FILE) | tail -10; \
	fi
	@echo ""
	@echo "❌ ERREURS D'EMAIL:"
	@echo "------------------"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep -E "(ERROR.*email|ERROR.*SMTP|ERROR.*mail)" $(LOGS_FILE) | tail -10; \
	fi

logs-full-report: ## Rapport complet (stats + erreurs + warnings + sécurité)
	@echo "📋 RAPPORT COMPLET DU SYSTÈME"
	@echo "============================="
	@echo ""
	@$(MAKE) logs-stats
	@echo ""
	@echo "🚨 PROBLÈMES DÉTECTÉS:"
	@echo "====================="
	@$(MAKE) logs-errors-and-warnings
	@echo ""
	@echo "🛡️  AUDIT SÉCURITÉ:"
	@echo "=================="
	@$(MAKE) logs-security-audit

logs-troubleshoot: ## Guide de dépannage automatique
	@echo "🔧 GUIDE DE DÉPANNAGE AUTOMATIQUE"
	@echo "================================="
	@echo ""
	@echo "📊 1. STATISTIQUES GÉNÉRALES:"
	@$(MAKE) logs-stats
	@echo ""
	@echo "❌ 2. ERREURS RÉCENTES (5 dernières):"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "ERROR" $(LOGS_FILE) | tail -5; \
	fi
	@echo ""
	@echo "⚠️  3. WARNINGS RÉCENTS (5 derniers):"
	@if [ -f "$(LOGS_FILE)" ]; then \
		grep "WARNING" $(LOGS_FILE) | tail -5; \
	fi
	@echo ""
	@echo "🔍 4. MODULES LES PLUS ACTIFS:"
	@if [ -f "$(LOGS_FILE)" ]; then \
		cut -d'-' -f3 $(LOGS_FILE) | sort | uniq -c | sort -nr | head -5; \
	fi
	@echo ""
	@echo "💡 SUGGESTIONS:"
	@echo "- Si beaucoup d'erreurs → make logs-error"
	@echo "- Si problème de connexion → make logs-auth"
	@echo "- Si lenteur → make logs-performance-check"
	@echo "- Si problème plugin → make logs-plugins-status"

logs-debug-session: ## Session de debug interactive
	@echo "🔍 SESSION DE DEBUG INTERACTIVE"
	@echo "==============================="
	@echo ""
	@echo "📋 Choisissez votre analyse:"
	@echo "1. Erreurs récentes       → make logs-error"
	@echo "2. Problèmes d'auth       → make logs-security-audit"
	@echo "3. Performance            → make logs-performance-check"
	@echo "4. État des plugins       → make logs-plugins-status"
	@echo "5. Activité utilisateurs  → make logs-user-activity"
	@echo "6. Santé de la DB         → make logs-database-health"
	@echo "7. Rapport complet        → make logs-full-report"
	@echo "8. Logs en temps réel     → make logs-live"
	@echo ""
	@echo "💡 Exemple: make logs-security-audit"

logs-watch-errors: ## Surveillance continue des erreurs (toutes les 10 secondes)
	@echo "👀 SURVEILLANCE CONTINUE DES ERREURS"
	@echo "====================================="
	@echo "🔄 Mise à jour toutes les 10 secondes (Ctrl+C pour arrêter)"
	@echo ""
	@while true; do \
		clear; \
		echo "🕐 $$(date '+%H:%M:%S') - Surveillance des erreurs"; \
		echo "=========================================="; \
		if [ -f "$(LOGS_FILE)" ]; then \
			echo "❌ ERREURS ($$(grep -c 'ERROR' $(LOGS_FILE) || echo 0)):"; \
			grep "ERROR" $(LOGS_FILE) | tail -5 || echo "Aucune erreur"; \
			echo ""; \
			echo "⚠️  WARNINGS ($$(grep -c 'WARNING' $(LOGS_FILE) || echo 0)):"; \
			grep "WARNING" $(LOGS_FILE) | tail -3 || echo "Aucun warning"; \
		else \
			echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
		fi; \
		sleep 10; \
	done

logs-smart-filter: ## Filtre intelligent basé sur le contexte
	@echo "🧠 FILTRE INTELLIGENT"
	@echo "===================="
	@echo ""
	@echo "🔍 Analyse automatique du contexte..."
	@if [ -f "$(LOGS_FILE)" ]; then \
		ERROR_COUNT=$$(grep -c 'ERROR' $(LOGS_FILE) || echo 0); \
		WARNING_COUNT=$$(grep -c 'WARNING' $(LOGS_FILE) || echo 0); \
		CRITICAL_COUNT=$$(grep -c 'CRITICAL' $(LOGS_FILE) || echo 0); \
		echo "📊 Erreurs: $$ERROR_COUNT | Warnings: $$WARNING_COUNT | Critiques: $$CRITICAL_COUNT"; \
		echo ""; \
		if [ $$CRITICAL_COUNT -gt 0 ]; then \
			echo "🚨 ALERTES CRITIQUES DÉTECTÉES!"; \
			echo "==============================="; \
			grep "CRITICAL" $(LOGS_FILE) | tail -10; \
		elif [ $$ERROR_COUNT -gt 10 ]; then \
			echo "❌ BEAUCOUP D'ERREURS DÉTECTÉES!"; \
			echo "==============================="; \
			grep "ERROR" $(LOGS_FILE) | tail -10; \
		elif [ $$WARNING_COUNT -gt 20 ]; then \
			echo "⚠️  NOMBREUX AVERTISSEMENTS!"; \
			echo "==========================="; \
			grep "WARNING" $(LOGS_FILE) | tail -10; \
		else \
			echo "✅ SYSTÈME STABLE - Logs récents:"; \
			echo "================================="; \
			tail -20 $(LOGS_FILE); \
		fi; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-timeline: ## Timeline des événements importants
	@echo "📅 TIMELINE DES ÉVÉNEMENTS"
	@echo "=========================="
	@echo ""
	@if [ -f "$(LOGS_FILE)" ]; then \
		echo "🕐 DERNIERS ÉVÉNEMENTS CRITIQUES:"; \
		echo "---------------------------------"; \
		grep -E "(CRITICAL|ERROR|Démarrage|Arrêt|startup|shutdown)" $(LOGS_FILE) | tail -15; \
		echo ""; \
		echo "🔐 DERNIÈRES CONNEXIONS:"; \
		echo "------------------------"; \
		grep -E "(connexion|login|logout)" $(LOGS_FILE) | tail -10; \
		echo ""; \
		echo "🔌 DERNIÈRES ACTIVITÉS PLUGINS:"; \
		echo "-------------------------------"; \
		grep -E "(Plugin.*ajouté|plugin.*chargé)" $(LOGS_FILE) | tail -5; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-health-check: ## Check-up santé complet du système (PRO)
	@echo "🏥 CHECK-UP SANTÉ DU SYSTÈME - VERSION PRO"
	@echo "========================================"
	@echo ""
	@if [ -f "$(LOGS_FILE)" ]; then \
		TOTAL_LINES=$$(wc -l < $(LOGS_FILE)); \
		ERROR_COUNT=$$(grep -c 'ERROR' $(LOGS_FILE) || echo 0); \
		WARNING_COUNT=$$(grep -c 'WARNING' $(LOGS_FILE) || echo 0); \
		CRITICAL_COUNT=$$(grep -c 'CRITICAL' $(LOGS_FILE) || echo 0); \
		INFO_COUNT=$$(grep -c 'INFO' $(LOGS_FILE) || echo 0); \
		\
		ERROR_THRESHOLD=5; \
		WARNING_THRESHOLD=10; \
		\
		echo "📊 MÉTRIQUES GLOBALES:"; \
		echo "---------------------"; \
		echo "📋 Total logs: $$TOTAL_LINES"; \
		echo "ℹ️  Info: $$INFO_COUNT"; \
		echo "⚠️  Warnings: $$WARNING_COUNT"; \
		echo "❌ Erreurs: $$ERROR_COUNT"; \
		echo "🚨 Critiques: $$CRITICAL_COUNT"; \
		\
		if [ $$CRITICAL_COUNT -gt 0 ]; then \
			echo -e "\033[1;41m🚨 ÉTAT: CRITIQUE\033[0m"; \
		elif [ $$ERROR_COUNT -gt $$ERROR_THRESHOLD ]; then \
			echo -e "\033[1;33m❌ ÉTAT: PROBLÉMATIQUE\033[0m"; \
		elif [ $$WARNING_COUNT -gt $$WARNING_THRESHOLD ]; then \
			echo -e "\033[1;33m⚠️  ÉTAT: ATTENTION REQUISE\033[0m"; \
		else \
			echo -e "\033[1;32m✅ ÉTAT: SAIN\033[0m"; \
		fi; \
		echo ""; \
		\
		echo "🔧 ACTIVITÉ PAR MODULE:"; \
		echo "---------------------"; \
		printf "%-20s %-10s %-10s %-10s\n" "MODULE" "TOTAL" "ERROR" "WARNING"; \
		awk -F ' - ' '{modules[$$2]++; if($$3=="ERROR") e[$$2]++; if($$3=="WARNING") w[$$2]++} \
			END {for (m in modules) printf "%-20s %-10d %-10d %-10d\n", m, modules[m], e[m]+0, w[m]+0}' $(LOGS_FILE) \
			| sort -k2 -nr; \
		\
		echo ""; \
		echo "🕐 DERNIÈRE ACTIVITÉ:"; \
		echo "--------------------"; \
		tail -5 $(LOGS_FILE); \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

logs-comparison: ## Compare les logs avant/après ($(LOGS_FILE) vs $(LOGS_FILE).old)
	@echo "🔄 COMPARAISON DES LOGS"
	@echo "======================"
	@echo ""
	@if [ -f "$(LOGS_FILE).old" ] && [ -f "$(LOGS_FILE)" ]; then \
		OLD_LINES=$$(wc -l < $(LOGS_FILE).old); \
		NEW_LINES=$$(wc -l < $(LOGS_FILE)); \
		DIFF_LINES=$$((NEW_LINES - OLD_LINES)); \
		echo "📊 Anciennes logs: $$OLD_LINES lignes"; \
		echo "📊 Nouvelles logs: $$NEW_LINES lignes"; \
		echo "📈 Différence: $$DIFF_LINES nouvelles lignes"; \
		echo ""; \
		if [ $$DIFF_LINES -gt 0 ]; then \
			echo "🆕 NOUVELLES ENTRÉES:"; \
			echo "--------------------"; \
			tail -n $$DIFF_LINES $(LOGS_FILE); \
		else \
			echo "ℹ️  Aucune nouvelle entrée depuis la dernière sauvegarde"; \
		fi; \
	else \
		echo "⚠️  Fichiers de comparaison non disponibles"; \
		echo "💡 Utilisez 'make logs-clean' pour créer $(LOGS_FILE).old"; \
	fi

logs-alerts: ## Alertes automatiques basées sur les patterns
	@echo "🚨 SYSTÈME D'ALERTES AUTOMATIQUES"
	@echo "================================="
	@echo ""
	@if [ -f "$(LOGS_FILE)" ]; then \
		echo "🔍 Analyse des patterns dangereux..."; \
		echo ""; \
		\
		FAILED_LOGINS=$$(grep -c "Échec de connexion\|Invalid credentials" $(LOGS_FILE) || echo 0); \
		if [ $$FAILED_LOGINS -gt 3 ]; then \
			echo "🚨 ALERTE: $$FAILED_LOGINS tentatives de connexion échouées!"; \
		fi; \
		\
		SMTP_ERRORS=$$(grep -c "ERROR.*SMTP\|ERROR.*email" $(LOGS_FILE) || echo 0); \
		if [ $$SMTP_ERRORS -gt 0 ]; then \
			echo "📧 ALERTE: $$SMTP_ERRORS erreurs d'email détectées!"; \
		fi; \
		\
		DB_ERRORS=$$(grep -c "ERROR.*database\|ERROR.*DB" $(LOGS_FILE) || echo 0); \
		if [ $$DB_ERRORS -gt 0 ]; then \
			echo "🗃️  ALERTE: $$DB_ERRORS erreurs de base de données!"; \
		fi; \
		\
		RECENT_ERRORS=$$(grep "ERROR" $(LOGS_FILE) | tail -10 | wc -l); \
		if [ $$RECENT_ERRORS -gt 5 ]; then \
			echo "⚡ ALERTE: Pic d'erreurs récent ($$RECENT_ERRORS erreurs récentes)!"; \
		fi; \
		\
		PLUGIN_ERRORS=$$(grep -c "ERROR.*plugin\|ERROR.*Plugin" $(LOGS_FILE) || echo 0); \
		if [ $$PLUGIN_ERRORS -gt 0 ]; then \
			echo "🔌 ALERTE: $$PLUGIN_ERRORS erreurs de plugins!"; \
		fi; \
		\
		if [ $$FAILED_LOGINS -eq 0 ] && [ $$SMTP_ERRORS -eq 0 ] && [ $$DB_ERRORS -eq 0 ] && [ $$RECENT_ERRORS -lt 5 ] && [ $$PLUGIN_ERRORS -eq 0 ]; then \
			echo "✅ Aucune alerte détectée - Système stable"; \
		fi; \
	else \
		echo "⚠️  Fichier $(LOGS_FILE) introuvable"; \
	fi

build: ## Build complet du projet (clean + install + lint-fix + format)
	@echo "🏗️  CONSTRUCTION DU PROJET"
	@echo "==========================="
	@echo ""
	@echo "🧹 1. Nettoyage des fichiers compilés..."
	@$(MAKE) clean
	@echo ""
	@echo "📦 2. Installation des dépendances..."
	@$(MAKE) install
	@echo ""
	@echo "🔧 3. Correction automatique du code..."
	@$(MAKE) lint-fix
	@echo ""
	@echo "✅ Build terminé avec succès!"

build-prod: ## Build pour production (build + tests + validation)
	@echo "🚀 BUILD PRODUCTION"
	@echo "=================="
	@echo ""
	@$(MAKE) build
	@echo ""
	@echo "🧪 5. Exécution des tests..."
	@$(MAKE) test
	@echo ""
	@echo "🔒 6. Validation sécurité..."
	@$(MAKE) security-check
	@echo ""
	@poetry build --no-cache
	@echo "🎉 Build production prêt!"


build-fast: ## Build rapide (clean + install uniquement)
	@echo "⚡ BUILD RAPIDE"
	@echo "=============="
	@$(MAKE) clean
	@$(MAKE) install
	@echo "✅ Build rapide terminé!"

lint-fix: ## Correction automatique des erreurs de linting (SAFE - préserve imports)
	@echo "🔧 Correction automatique du code (mode SAFE)..."
	@echo "📋 1. Correction autopep8 (lignes longues, espaces)..."
	@poetry run autopep8 --in-place --recursive --exclude=alembic,static,__pycache__ .
	@echo "📋 2. Tri des imports avec isort..."
	@poetry run isort . --skip=alembic --skip=static --skip=__pycache__
	@echo "📋 3. Formatage avec black..."
	@poetry run black . --exclude="(alembic|static|__pycache__)"
	@echo "📋 4. Suppression CONSERVATIVE des variables inutiles (préserve imports)..."
	@poetry run autoflake --in-place --recursive --remove-unused-variables --ignore-init-module-imports --exclude=alembic,static,__pycache__ .
	@echo "✅ Correction automatique terminée (imports préservés)!"

lint-check: ## Vérifier le linting sans modifier les fichiers (pour le CI)
	@echo "🔍 Vérification du code (mode CHECK)..."
	@echo "📋 1. Vérification black..."
	@poetry run black . --check --exclude="(alembic|static|__pycache__)"
	@echo "📋 2. Vérification isort..."
	@poetry run isort . --check-only --skip=alembic --skip=static --skip=__pycache__
	@echo "📋 3. Vérification flake8..."
	@poetry run flake8 .
	@echo "✅ Vérification terminée!"

pre-commit-install: ## Installer les hooks de pre-commit
	@echo "📥 Installation des hooks pre-commit..."
	@poetry run pre-commit install

pre-commit-run: ## Lancer manuellement les hooks sur tous les fichiers
	@echo "🚀 Lancement de pre-commit sur tous les fichiers..."
	@poetry run pre-commit run --all-files

pre-commit: pre-commit-run ## Alias pour pre-commit-run

validate-plugins: ## Valider tous les plugins (structure + AST)
	@echo "🔌 Validation des plugins..."
	@poetry run xcore plugin health

auto-fix: ## Alias pour lint-fix (correction automatique sécurisée)
	@$(MAKE) lint-fix

lint-preview: ## Prévisualiser les corrections sans les appliquer
	@echo "👀 Prévisualisation des corrections autopep8:"
	@poetry run autopep8 --diff --recursive --exclude=alembic,static,__pycache__ . | head -50
	@echo ""
	@echo "👀 Prévisualisation du formatage black:"
	@poetry run black --diff . --exclude="(alembic|static|__pycache__)" | head -30

lint-safe: ## Linting avec configuration adaptée à FastHTML
	@echo "🔍 Vérification du code (compatible FastHTML)..."
	@poetry run flake8 .

test: ## Exécution des tests
	@echo "🧪 Exécution des tests..."
	@if [ -d "tests" ]; then \
		poetry run pytest tests/ --cov --cov-branch --cov=src --cov-report=xml; \
	else \
		echo "⚠️  Dossier tests/ non trouvé"; \
		echo "💡 Créez des tests pour améliorer la qualité"; \
		fi

benchmark: ## Exécuter les tests de benchmark avec pytest-benchmark
	@echo "⏱️  Exécution des benchmarks..."
	@poetry run pytest tests/benchmarks/test_kernel_benchmarks.py --benchmark-only --benchmark-group-by=group --benchmark-warmup=on

security-check: ## Vérification de sécurité basique
	@echo "🔒 Vérification de sécurité..."
	@echo "✅ Vérification .env (ne pas commiter)"
	@if git ls-files | grep -q "\.env$$"; then \
		echo "❌ ATTENTION: .env est tracké par git!"; \
	else \
		echo "✅ .env correctement ignoré"; \
	fi
	@echo "✅ Vérification des mots de passe hardcodés..."
	@if grep -r "password\s*=\s*[\"'][^\"']*[\"']" . --exclude-dir=.git --exclude-dir=static --exclude-dir=__pycache__ 2>/dev/null; then \
		echo "❌ ATTENTION: Mots de passe potentiels trouvés!"; \
	else \
		echo "✅ Aucun mot de passe hardcodé détecté"; \
	fi
	@echo "✅ VALIDATION DU PROJET"
	@echo "====================="
	@echo ""
	@echo "🔍 1. Syntaxe Python..."
	@poetry run python -m py_compile main.py
	@echo ""
	@echo "📦 2. Dépendances..."
	@poetry check
	@echo ""
	@echo "🔧 3. Configuration..."
	@if [ -f ".env" ]; then \
		echo "✅ Fichier .env présent"; \
	else \
		echo "⚠️  Fichier .env manquant"; \
	fi
	@echo ""
	@echo "✅ Validation terminée!"


	@echo "🧹 Nettoyage Docker..."
	@sudo docker compose down -v
	@sudo docker system prune -f
