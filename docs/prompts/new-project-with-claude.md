# Prompt: nuevo proyecto con Claude Code en Codespaces

Usa este prompt dentro de Claude Code desde la terminal Linux remota del repo:

```text
Actua como arquitecto senior y senior full-stack/platform engineer.

Contexto:
- Estoy trabajando en un Codespace/Linux remoto, no en Windows local.
- El repo actual es la fuente de verdad y vive en GitHub.
- El workspace debe estar en /workspaces/<repo>.
- No se debe usar AWS, EC2, SSM, NAT Gateway ni CloudShell.
- No se deben guardar secretos en Git.
- No se deben guardar API keys en .bashrc, .profile, .env, devcontainer, README ni GitHub Actions.

Objetivo:
Inspecciona el repo, propone una arquitectura minima y crea un MVP funcional.

Tareas:
1. Inspecciona estructura, stack, scripts, tests y documentacion existentes.
2. Resume riesgos y decisiones antes de hacer cambios grandes.
3. Propone una arquitectura simple, mantenible y adecuada al objetivo del proyecto.
4. Implementa el MVP con cambios pequenos y cohesionados.
5. Crea o actualiza README.md con instrucciones de uso.
6. Crea o actualiza docs/ si el flujo necesita explicacion.
7. Anade tests proporcionados al riesgo del cambio.
8. Anade scripts de build/test si el stack los necesita.
9. Mantiene .devcontainer sin secretos y con herramientas reproducibles.
10. Verifica con comandos reales: git status, tests, build o scripts aplicables.
11. Prepara commits pequenos y claros.

Reglas:
- No metas secretos ni placeholders reales de credenciales.
- Si necesitas una clave, pide que se exporte temporalmente en la sesion.
- No instales Claude Code ni herramientas en Windows local como solucion principal.
- No introduzcas servicios cloud innecesarios.
- Prefiere soluciones simples y operativas.
- No hagas refactors grandes sin necesidad.
- No borres cambios existentes sin explicar por que.

Formato de trabajo:
1. Diagnostico breve.
2. Plan de cambios.
3. Implementacion.
4. Validacion.
5. Resumen de archivos tocados.
6. Siguiente paso recomendado.
```

Comandos previos recomendados:

```bash
cd /workspaces/<repo>
hostname
pwd
whoami
git status
node --version
npm --version
python3 --version
claude --version
claude
```
