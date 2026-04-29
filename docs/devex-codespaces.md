# DevEx: Codespaces, VS Code local, Remote Tunnel, Claude Code

## Goal

Work on `paper-monitor` from VS Code Desktop using a Linux cloud environment backed by GitHub Codespaces.

Target path:

```text
VS Code local -> remote/tunnel -> Codespace Linux -> /workspaces/paper-monitor -> Claude Code
```

Hard rules:

- Do not use AWS for the daily workflow.
- Do not recreate EC2.
- Do not use SSM, NAT Gateway, CloudShell, or AWS Toolkit.
- Do not store secrets in the repo, `.env`, shell profiles, devcontainer config, or GitHub Actions.
- Claude Code runs inside the Codespace, not on Windows local.

## Local VS Code diagnostic

1. Close the old remote session if VS Code still shows it.

   If the green remote indicator or recent windows show `ip-10-42-1-168`, run:

   ```text
   Remote: Close Remote Connection
   ```

2. Verify the required local extensions:

   ```powershell
   code --list-extensions --show-versions
   ```

   Required:

   ```text
   github.codespaces
   ms-vscode.remote-server
   ```

   Useful:

   ```text
   github.vscode-pull-request-github
   ```

   Install missing extensions from VS Code or with:

   ```powershell
   code --install-extension github.codespaces
   code --install-extension ms-vscode.remote-server
   code --install-extension github.vscode-pull-request-github
   ```

3. Verify the GitHub account in VS Code.

   Open the Accounts menu in VS Code and confirm the signed-in GitHub account is the same account that can open:

   ```text
   https://github.com/codespaces
   ```

## Codespace diagnostic

1. Open:

   ```text
   https://github.com/codespaces
   ```

2. Confirm there is a Codespace for:

   ```text
   JavierAldea78/paper-monitor
   ```

3. Confirm:

   ```text
   State: Running
   Repo: JavierAldea78/paper-monitor
   Branch: main, or the branch you intend to edit
   ```

4. In VS Code local, try the normal path first:

   ```text
   Codespaces: Connect to Codespace
   ```

5. If it fails, collect this before changing strategy:

   ```text
   Exact error message
   View -> Output -> GitHub Codespaces
   VS Code version
   GitHub Codespaces extension version
   Whether the failure looks like authentication, proxy, WebSocket, port blocking, or policy
   ```

   Useful commands:

   ```powershell
   code --version
   code --list-extensions --show-versions
   ```

## Primary path: VS Code Desktop to Codespaces

Use this if `Codespaces: Connect to Codespace` works.

1. Open VS Code local.
2. Run:

   ```text
   Codespaces: Connect to Codespace
   ```

3. Select the `paper-monitor` Codespace.
4. Open the folder:

   ```text
   /workspaces/paper-monitor
   ```

5. Open a remote terminal and validate:

   ```bash
   hostname
   pwd
   whoami
   git status
   node --version
   npm --version
   python --version
   claude --version
   ```

Expected:

```text
pwd is /workspaces/paper-monitor
git status works
claude runs in the Codespace terminal
```

## Fallback path: Remote Tunnel from inside Codespaces

Use this if Codespaces works in the browser but VS Code Desktop cannot connect through the normal Codespaces extension path.

### Start tunnel when `code tunnel` exists

1. Open the Codespace in the browser from:

   ```text
   https://github.com/codespaces
   ```

2. Open a terminal inside the browser Codespace.

3. Validate the CLI:

   ```bash
   code --version
   code tunnel --help
   ```

4. Start the tunnel:

   ```bash
   code tunnel --name paper-monitor-codespace --accept-server-license-terms
   ```

5. Complete the GitHub device/browser login shown by the command.

6. In VS Code local, run:

   ```text
   Remote - Tunnels: Connect to Tunnel
   ```

7. Select:

   ```text
   paper-monitor-codespace
   ```

8. Open:

   ```text
   /workspaces/paper-monitor
   ```

Keep the browser Codespace and tunnel terminal alive while working. Stop the tunnel with `Ctrl+C` when done.

### Install VS Code CLI if `code tunnel` is missing

Run this inside the browser Codespace terminal:

```bash
mkdir -p "$HOME/.local/bin" "$HOME/.local/share/vscode-cli"
curl -fsSL "https://code.visualstudio.com/sha/download?build=stable&os=cli-linux-x64" -o /tmp/vscode_cli.tar.gz
tar -xzf /tmp/vscode_cli.tar.gz -C "$HOME/.local/share/vscode-cli"
ln -sf "$HOME/.local/share/vscode-cli/code" "$HOME/.local/bin/code"
export PATH="$HOME/.local/bin:$PATH"
code --version
code tunnel --help
```

If `cli-linux-x64` is not accepted by the download endpoint, retry the download with:

```bash
curl -fsSL "https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64" -o /tmp/vscode_cli.tar.gz
```

Then start the tunnel:

```bash
code tunnel --name paper-monitor-codespace --accept-server-license-terms
```

## Devcontainer

This repo includes:

```text
.devcontainer/devcontainer.json
.devcontainer/post-create.sh
```

The Codespace image provides:

```text
Node.js 20
npm
git
Python 3.12
```

The post-create script:

- Configures npm global packages under `~/.npm-global`.
- Adds `~/.npm-global/bin` and `~/.local/bin` to the user PATH.
- Installs Python dependencies from `requirements.txt`.
- Installs Claude Code with npm.
- Does not store secrets.
- Does not configure AWS.

## Claude Code in the Codespace

The devcontainer installs Claude Code automatically:

```bash
npm install -g @anthropic-ai/claude-code
```

Manual reinstall, if needed:

```bash
mkdir -p "$HOME/.npm-global/bin"
npm config set prefix "$HOME/.npm-global"
export PATH="$HOME/.npm-global/bin:$PATH"
npm install -g @anthropic-ai/claude-code
claude --version
```

If Claude asks for authentication, use its browser/device login flow. Do not write API keys to the repo, `.env`, `.bashrc`, `.profile`, devcontainer config, or GitHub Actions.

## Final validation checklist

Run these from the VS Code local terminal after connecting to the Codespace or tunnel:

```bash
hostname
pwd
whoami
git status
node --version
npm --version
python --version
claude --version
```

Expected result:

```text
pwd: /workspaces/paper-monitor
git status: works
node/npm: available
python: available
claude: runs inside the Codespace
```

## Cost and operation

- Codespaces consumes GitHub quota.
- Running Codespaces consume CPU quota.
- Stopped Codespaces may still consume storage quota.
- Stop the Codespace when not using it:

  ```text
  Codespaces: Stop Codespace
  ```

  Or from:

  ```text
  https://github.com/codespaces
  ```

- Delete old Codespaces you no longer need from:

  ```text
  https://github.com/codespaces
  ```

- GitHub is the source of truth.
- There is no AWS daily development path.
- There is no EC2, SSM, NAT Gateway, or CloudShell dependency.

## Troubleshooting

### Browser Codespaces works, VS Code Desktop does not

Use the tunnel fallback:

```bash
code tunnel --name paper-monitor-codespace --accept-server-license-terms
```

Then connect from VS Code local with:

```text
Remote - Tunnels: Connect to Tunnel
```

### Authentication failure

In VS Code local:

1. Sign out of GitHub.
2. Sign in again from the Accounts menu.
3. Confirm it is the same account that owns or can access the Codespace.
4. Retry:

   ```text
   Codespaces: Connect to Codespace
   ```

### Proxy, WebSocket, or corporate policy failure

Collect:

```text
View -> Output -> GitHub Codespaces
View -> Output -> Remote - Tunnels
```

Then use the tunnel fallback from inside the browser Codespace. The browser path proves the backend is healthy; the tunnel path avoids depending on the failing Codespaces desktop route.

### Wrong remote still open

If VS Code shows `ip-10-42-1-168`, close it:

```text
Remote: Close Remote Connection
```

Then connect to the Codespace or tunnel again.

### Claude command missing

Run inside the Codespace:

```bash
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$PATH"
npm config get prefix
npm install -g @anthropic-ai/claude-code
claude --version
```

### Stop and clean tunnel

Stop the active tunnel:

```text
Ctrl+C
```

Unregister a stale tunnel from inside the Codespace:

```bash
code tunnel unregister
```
