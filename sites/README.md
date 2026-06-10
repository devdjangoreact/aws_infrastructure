# Sites (Git Submodules)

Each site is a standalone GitHub repository wired into this infra-repo as a Git submodule.
The folder/project name differs from the public domain; the table below is the source of truth.

| Project (submodule) | Repository | Domain | Service / ECR image |
|---------------------|------------|--------|---------------------|
| `course_hub` | `devdjangoreact/course_hub` | `ddnsteltonicka.pp.ua` | `ddnsteltonicka` |
| `cosmetic` | `devdjangoreact/cosmetic` | `cosmeticpro.pp.ua` | `cosmeticpro` |
| `apifypro` | `devdjangoreact/apifypro` | `codehelp.pp.ua` | `codehelp` |
| `botnet` | `devdjangoreact/botnet` | `buyraq.com` | `buyraq` |
| `arbitrator` | `devdjangoreact/arbitrator` | `solovkadmytro.pp.ua` | `solovkadmytro` |
| `lengia` | `devdjangoreact/lengia` | `solovkaskincare.pp.ua` | `solovkaskincare` |

`SERVICE_NAME` and `DOMAIN` are set as GitHub Actions repository variables in each app-repo so the
ECR image name and Traefik routing keep matching the infra `docker-compose.yml`, `deploy.sh`,
and `validate.sh` (which stay keyed by the service name, not the project name).

## Clone the infra-repo with all sites

```bash
git clone --recurse-submodules https://github.com/devdjangoreact/infra.git
# or, if already cloned without submodules:
git submodule update --init --recursive
```

The site repos are private, so cloning needs a credential helper or a token-backed remote.

## Update one site to its latest commit

```bash
git -C sites/<project> pull origin main
git add sites/<project>
git commit -m "Bump <project> submodule"
```

Then push the infra-repo so the recorded submodule commit advances.

## Update all sites at once

```bash
git submodule update --remote --merge
git add sites
git commit -m "Bump all site submodules"
```

## Add a new site

```bash
git submodule add https://github.com/devdjangoreact/<repo>.git sites/<repo>
git commit -m "Add <repo> submodule"
```

## Remove a site

```bash
git submodule deinit -f sites/<project>
git rm -f sites/<project>
rm -rf .git/modules/sites/<project>
git commit -m "Remove <project> submodule"
```

## How a deploy happens (easy AWS update)

1. Edit `index.html` in a site repo and push to its `main` branch.
2. The site repo's `.github/workflows/build.yml` builds the `nginx:alpine` image and pushes
   `:latest` and `:<sha>` to Amazon ECR Public.
3. It then sends a `repository_dispatch` (`deploy`) event to `devdjangoreact/infra`, which pulls
   the new image and restarts only that container on the EC2 host.

Each site is intentionally a minimal Docker container (single static `index.html`) for fast,
low-risk updates.
