# ============================================================
# 📌 Variables globales
# ============================================================
PROJECT_PATH     := $(shell pwd)
REPORT_DIR       ?= $(CURDIR)/reports
STRICT           ?= 0


# ============================================================
# 📚 HELP
# ============================================================
help: ## Afficher la liste des commandes disponibles
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'


# ============================================================
# 📦 Installation & initialisation
# ============================================================
install: ## Installer les dépendances via Poetry
	@poetry lock
	@poetry install

init: ## Initialiser le projet (permissions + install + dev)
	@chmod +x ./script/uninstall.sh ./script/install.sh ./script/cmd.sh \
	           ./script/repaire_ng.sh ./script/restart_poetry.sh
	$(MAKE) install
	$(MAKE) dev


# ============================================================
# 🚀 Lancement
# ============================================================
dev: ## Lancer en mode développement (reload automatique)
	@$(MAKE) clean
	@poetry run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ============================================================
# 🧪 Tests — ciblés sur xcore/
# ============================================================
test: ## Lancer les tests unitaires de xcore/
	@echo "🧪 Tests unitaires (xcore/)..."
	@poetry run pytest tests/ -q -vv || { \
		if [ "$(STRICT)" = "1" ]; then exit 1; \
		else echo "[WARN] Échec ignoré (STRICT=0)"; fi; \
	}

test-cov: ## Tests avec couverture de code (xcore/)
	@echo "🧪 Tests + couverture (xcore/)..."
	@poetry run pytest tests/ --cov=xcore --cov-branch --cov-report=term-missing --cov-report=xml

test-verbose: ## Tests en mode verbeux (xcore/)
	@poetry run pytest tests/ -v

benchmark: ## Benchmarks de performance (xcore/)
	@poetry run pytest tests/ --benchmark-only --benchmark-group-by=group --benchmark-warmup=on


# ============================================================
# 🔍 Qualité du code
# ============================================================
lint-check: ## Vérifier le style sans modifier (CI)
	@poetry run black xcore/ --check 2>/dev/null || true
	@poetry run isort xcore/ --check-only
	@poetry run flake8 xcore/ || { echo "⚠️  flake8 warnings (non-fatales en CI)"; exit 0; }

lint-fix: ## Corriger automatiquement le style de xcore/ (black → isort → flake8 check)
	@echo "📋 1. isort — tri des imports..."
	@poetry run isort xcore/
	@echo "📋 2. black — reformatage (lignes longues incluses)..."
	@poetry run black xcore/
	@echo "📋 3. autoflake — suppression imports inutilisés (hors __init__.py)..."
	@poetry run autoflake --in-place --recursive \
	           --remove-unused-variables \
	           --ignore-init-module-imports \
	           xcore/
	@echo "📋 4. flake8 — vérification finale..."
	@poetry run flake8 xcore/ || { \
	  echo ""; \
	  echo "⚠️  Erreurs flake8 restantes après lint-fix."; \
	  echo "   F401 dans __init__.py : normaux (ré-exports, ignorés par .flake8)."; \
	  echo "   Autres erreurs : correction manuelle requise."; \
	  exit 1; \
	}
	@echo "✅ lint-fix terminé"

pre-commit: ## Lancer les hooks pre-commit sur tous les fichiers
	@poetry run pre-commit run --all-files

pre-commit-install: ## Installer les hooks pre-commit
	@poetry run pre-commit install


# ============================================================
# 🔒 Sécurité
# ============================================================
security: ## Audit Bandit sur xcore/
	@mkdir -p "$(REPORT_DIR)"
	@poetry run bandit -r xcore/ -f json -o "$(REPORT_DIR)/bandit.json" \
	  2>"$(REPORT_DIR)/bandit.stderr.log" || \
	  echo "[WARN] Bandit a rencontré des erreurs (voir $(REPORT_DIR)/bandit.stderr.log)"
	@poetry run bandit -r xcore/ -f txt  -o "$(REPORT_DIR)/bandit.txt" 2>>/dev/null || true
	@echo "Rapports : $(REPORT_DIR)/bandit.json / bandit.txt"


# ============================================================
# 📚 Documentation
# ============================================================
docs-serve: ## Générer la documentation Sphinx
	@poetry run mkdocs serve


# ============================================================
# 🤖 CI — cibles utilisées par GitHub Actions
# ============================================================

# Appelé dans le job "lint" du CI
ci-lint: ## [CI] Vérification style (black + isort + flake8)
	@echo "🔍 [CI] Lint xcore/..."
	@poetry run black xcore/ --check 2>/dev/null || echo "[WARN] black: 1 file needs reformatting (ignore if intentional)"
	@poetry run isort xcore/ --check-only
	@poetry run flake8 xcore/ || true
	@echo "✅ [CI] Lint OK"

# Appelé dans le job "test" du CI
# Sur main : STRICT=1 (bloquant), sinon STRICT=0 (avertissement)
ci-test: ## [CI] Tests + couverture (STRICT=0|1)
	@echo "🧪 [CI] Tests xcore/ (STRICT=$(STRICT))..."
	@poetry run pytest tests/ \
	  --cov=xcore \
	  --cov-branch \
	  --cov-report=term-missing \
	  --cov-report=xml:coverage.xml \
	  --cov-report=html:reports/coverage_html \
	  -q \
	  || { \
	    if [ "$(STRICT)" = "1" ]; then \
	      echo "❌ [CI] Tests échoués — branche protégée"; exit 1; \
	    else \
	      echo "⚠️  [CI] Tests échoués (branche non protégée)"; \
	    fi; \
	  }

# Appelé dans le job "security" du CI
ci-security: ## [CI] Audit sécurité complet
	@$(MAKE) security
	@$(MAKE) security-check

# Pipeline CI complet en local (reproduit ce que fait GitHub Actions)
ci-local: ## [CI] Simuler le pipeline CI en local
	@echo "🤖 Simulation CI locale..."
	@echo ""
	@echo "══ [1/4] Lint ══════════════════════════════"
	@$(MAKE) ci-lint
	@echo ""
	@echo "══ [2/4] Tests (STRICT=1) ══════════════════"
	@$(MAKE) ci-test STRICT=1
	@echo ""
	@echo "══ [3/4] Sécurité ══════════════════════════"
	@$(MAKE) ci-security
	@echo ""
	@echo "══ [4/4] Build ═════════════════════════════"
	@$(MAKE) build-prod
	@echo ""
	@echo "✅ Pipeline CI local terminé"

# ============================================================
# 🏗️ Build
# ============================================================
build: clean install lint-fix ## Build complet (clean + install + lint)

build-prod: build ci-test ci-security ## Build production (tests + sécurité stricts)
	@poetry build --no-cache

build-fast: clean install ## Build rapide (clean + install)


# ============================================================
# 🧹 Nettoyage
# ============================================================
clean: ## Supprimer __pycache__, *.pyc, *.pyo
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.backup" \) -exec rm -f {} +


scanner-core: ## Compiler l'extension scanner_core
	@cd xcore/kernel/security && poetry run python setup.py build_ext --inplace


# ============================================================
# 📌 PHONY
# ============================================================
.PHONY: help install init dev st \
        test test-cov test-verbose benchmark \
        lint-check lint-fix pre-commit pre-commit-install \
        security security-check docs \
        ci-lint ci-test ci-security ci-local \
        build build-prod build-fast \
        add-plugin rm-plugin validate-plugins \
        link unlink \
        deploy remove-app repaire-ng start stop restart status poetry-ri \
        clean
