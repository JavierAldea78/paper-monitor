# DevEx reusable: VS Code local, GitHub Codespaces, Claude Code

## Arquitectura objetivo

```text
VS Code local
-> GitHub Codespaces o Linux remoto equivalente
-> repo en /workspaces/<repo>
-> terminal integrada Linux
-> Claude Code dentro del entorno remoto
```

Este patron evita AWS para el flujo diario. No usa EC2, SSM, NAT Gateway, CloudShell ni secretos persistentes.

## Diagnostico actual de VS Code local

Estado observado en esta maquina:

```text
VS Code: 1.117.0
GitHub Codespaces extension: github.codespaces@1.18.13
Remote - Tunnels extension: ms-vscode.remote-server@1.5.3
GitHub Pull Requests extension: no instalada en local, recomendada
```

Tambien queda historial local del remoto antiguo:

```text
tunnel+ip-10-42-1-168
```

Si VS Code muestra esa maquina o una IP tipo `ip-10-42-1-168`, ejecutar desde la Command Palette:

```text
Remote: Close Remote Connection
```

No borrar manualmente `globalStorage` salvo que se quiera limpiar historial de VS Code de forma deliberada.

## Validar VS Code local

Ejecutar en Windows:

```powershell
code --version
code --list-extensions --show-versions
```

Debe aparecer:

```text
github.codespaces
ms-vscode.remote-server
```

Instalar extensiones si faltan:

```powershell
code --install-extension github.codespaces
code --install-extension ms-vscode.remote-server
code --install-extension github.vscode-pull-request-github
```

Validar autenticacion GitHub:

1. Abrir VS Code local.
2. Abrir el menu Accounts.
3. Confirmar sesion GitHub activa.
4. Confirmar que es la misma cuenta que abre el repo en:

   ```text
   https://github.com/codespaces
   ```

## Crear un repo nuevo en GitHub

Opcion recomendada:

1. Crear el repo vacio desde GitHub web.
2. No anadir secretos al repo.
3. Abrir el repo en Codespaces.

Comandos iniciales si se arranca desde una terminal Linux remota:

```bash
mkdir my-project
cd my-project
git init
mkdir -p docs src tests .github/workflows .devcontainer
touch README.md SECURITY.md .gitignore
git add .
git commit -m "chore: initial project structure"
git branch -M main
git remote add origin https://github.com/<owner>/<repo>.git
git push -u origin main
```

Estructura minima:

```text
README.md
SECURITY.md
.gitignore
.devcontainer/
docs/
src/ or app/
tests/
.github/workflows/
```

`.gitignore` minimo:

```gitignore
.env
.env.*
!.env.example
__pycache__/
*.pyc
node_modules/
dist/
build/
.pytest_cache/
.coverage
.DS_Store
```

## Abrir un repo en Codespaces

Desde navegador:

1. Abrir el repo en GitHub.
2. Pulsar `Code`.
3. Seleccionar `Codespaces`.
4. Crear o abrir Codespace.

Desde VS Code local:

```text
Codespaces: Connect to Codespace
```

Seleccionar el Codespace del repo.

El repo debe quedar en:

```text
/workspaces/<repo>
```

## Validar terminal Linux remota

En la terminal integrada de VS Code conectado al Codespace:

```bash
hostname
pwd
whoami
git status
```

Resultado esperado:

```text
pwd = /workspaces/<repo>
git status funciona
```

Validar herramientas:

```bash
git --version
node --version
npm --version
python3 --version
python3 -m pip --version
```

Si falta alguna herramienta, arreglarlo en `.devcontainer/devcontainer.json` o en `.devcontainer/post-create.sh`, no con parches manuales sueltos.

## Devcontainer base reutilizable

Copiar estos ficheros al repo:

```text
.devcontainer/devcontainer.json
.devcontainer/post-create.sh
```

`devcontainer.json` base:

```json
{
  "name": "codespaces-node-python-claude",
  "image": "mcr.microsoft.com/devcontainers/javascript-node:1-20-bookworm",
  "features": {
    "ghcr.io/devcontainers/features/python:1": {
      "version": "3.12"
    }
  },
  "remoteUser": "node",
  "containerUser": "node",
  "workspaceFolder": "/workspaces/${localWorkspaceFolderBasename}",
  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "davidanson.vscode-markdownlint",
        "github.vscode-pull-request-github"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/python/current/bin/python",
        "terminal.integrated.defaultProfile.linux": "bash"
      }
    }
  }
}
```

`post-create.sh` base:

```bash
#!/usr/bin/env bash
set -euo pipefail

repo_root="${CODESPACE_VSCODE_FOLDER:-$PWD}"
cd "$repo_root"

mkdir -p "$HOME/.npm-global/bin" "$HOME/.local/bin"
npm config set prefix "$HOME/.npm-global"

profile_line='export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"'
if ! grep -Fq "$profile_line" "$HOME/.bashrc" 2>/dev/null; then
  printf '\n%s\n' "$profile_line" >> "$HOME/.bashrc"
fi

export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"

python_bin="$(command -v python3 || command -v python)"
"$python_bin" -m pip install --user --upgrade pip
if [ -f requirements.txt ]; then
  "$python_bin" -m pip install --user -r requirements.txt
fi

npm install -g @anthropic-ai/claude-code

node --version
npm --version
"$python_bin" --version
git --version
claude --version
```

Para un repo con stack propio, adaptar el devcontainer sin romperlo:

- Node app: anadir `npm ci` solo si hay `package-lock.json`.
- Python app: usar `requirements.txt`, `pyproject.toml` o `uv` segun el repo.
- Web estatica: no instalar dependencias extra si no existen.
- Automatizaciones: mantener scripts bajo `scripts/` y tests bajo `tests/`.

## Claude Code dentro del Codespace

Instalacion principal dentro del Linux remoto:

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

Si falla por permisos:

```bash
mkdir -p "$HOME/.npm-global/bin"
npm config set prefix "$HOME/.npm-global"
export PATH="$HOME/.npm-global/bin:$PATH"
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> "$HOME/.bashrc"
npm install -g @anthropic-ai/claude-code
claude --version
```

Abrir Claude Code:

```bash
cd /workspaces/<repo>
claude
```

## Autenticacion de Claude Code

Opcion A: login interactivo.

```bash
claude
```

Usar el flujo browser/device que muestre Claude.

Opcion B: API key temporal solo en la sesion actual.

```bash
export ANTHROPIC_API_KEY="..."
claude
```

Reglas:

- No commitear claves.
- No guardar claves en `.bashrc`.
- No guardar claves en `.profile`.
- No guardar claves en `.env`.
- No guardar claves en devcontainer.
- No guardar claves en README.
- No guardar claves en GitHub Actions.

## Workaround con Remote Tunnel

Usar esto si Codespaces funciona en navegador pero VS Code Desktop no conecta por autenticacion, proxy, WebSocket, puerto o politica local.

Dentro del Codespace abierto en navegador:

```bash
code --version
code tunnel --help
code tunnel --name <repo>-codespace --accept-server-license-terms
```

Completar el device login.

En VS Code local:

```text
Remote - Tunnels: Connect to Tunnel
```

Seleccionar:

```text
<repo>-codespace
```

Abrir:

```text
/workspaces/<repo>
```

Si `code tunnel` no existe dentro del Codespace:

```bash
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/vscode-cli"
curl -fsSL "https://code.visualstudio.com/sha/download?build=stable&os=cli-linux-x64" -o /tmp/vscode_cli.tar.gz
tar -xzf /tmp/vscode_cli.tar.gz -C "$HOME/.local/share/vscode-cli"
ln -sf "$HOME/.local/share/vscode-cli/code" "$HOME/.local/bin/code"
export PATH="$HOME/.local/bin:$PATH"
code --version
code tunnel --help
```

Arrancar:

```bash
code tunnel --name <repo>-codespace --accept-server-license-terms
```

## Checklist de validacion

- [ ] VS Code local no esta conectado a AWS.
- [ ] Si aparece `ip-10-42-1-168`, se ejecuto `Remote: Close Remote Connection`.
- [ ] Extension `github.codespaces` instalada.
- [ ] Extension `ms-vscode.remote-server` instalada.
- [ ] VS Code autenticado con la cuenta GitHub correcta.
- [ ] Repo abierto en Codespaces.
- [ ] Terminal muestra Linux remoto.
- [ ] `pwd` esta en `/workspaces/<repo>`.
- [ ] `git status` funciona.
- [ ] `node --version` funciona.
- [ ] `npm --version` funciona.
- [ ] `python3 --version` funciona si aplica.
- [ ] `claude --version` funciona.
- [ ] `claude` abre correctamente.
- [ ] No hay secretos en repo.
- [ ] README explica el flujo.

## Coste y operacion

Codespaces consume cuota de GitHub.

Parar Codespace cuando no se use:

```text
Codespaces: Stop Codespace
```

O desde:

```text
https://github.com/codespaces
```

Eliminar Codespaces antiguos:

```text
https://github.com/codespaces
```

Reglas operativas:

- Un Codespace corriendo consume CPU quota.
- Un Codespace parado puede consumir storage quota.
- GitHub es la fuente de verdad.
- No hay AWS en el flujo diario.
- No hay EC2, SSM, NAT Gateway ni CloudShell.

## Troubleshooting

### Codespaces browser funciona, VS Code Desktop falla

1. Recoger:

   ```text
   View -> Output -> GitHub Codespaces
   View -> Output -> Remote - Tunnels
   ```

2. Usar Remote Tunnel desde el Codespace browser:

   ```bash
   code tunnel --name <repo>-codespace --accept-server-license-terms
   ```

3. Conectar desde VS Code local:

   ```text
   Remote - Tunnels: Connect to Tunnel
   ```

### GitHub no autentica en VS Code

1. Sign out de GitHub en VS Code.
2. Sign in otra vez.
3. Confirmar misma cuenta que abre `https://github.com/codespaces`.
4. Reintentar `Codespaces: Connect to Codespace`.

### Faltan herramientas en Linux remoto

No instalar a mano como solucion definitiva. Editar devcontainer y rebuild:

```text
Codespaces: Rebuild Container
```

### Claude no aparece en PATH

```bash
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
npm config get prefix
npm install -g @anthropic-ai/claude-code
claude --version
```

### Revisar secretos antes de commit

```bash
git status
git diff --cached
git diff
```

No subir `.env`, tokens, API keys ni credenciales.
