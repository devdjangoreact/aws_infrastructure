# Domain / Service Map

Each managed domain maps 1:1 to a service name, an app-repo, and a container.

| domain | service_name | app-repo | image (ECR Public) |
|--------|--------------|----------|--------------------|
| buyraq.com | buyraq | app-repo-1 | `public.ecr.aws/<alias>/buyraq` |
| codehelp.pp.ua | codehelp | app-repo-2 | `public.ecr.aws/<alias>/codehelp` |
| cosmeticpro.pp.ua | cosmeticpro | app-repo-3 | `public.ecr.aws/<alias>/cosmeticpro` |
| ddnsteltonicka.pp.ua | ddnsteltonicka | app-repo-4 | `public.ecr.aws/<alias>/ddnsteltonicka` |
| solovkadmytro.pp.ua | solovkadmytro | app-repo-5 | `public.ecr.aws/<alias>/solovkadmytro` |
| solovkaskincare.pp.ua | solovkaskincare | app-repo-6 | `public.ecr.aws/<alias>/solovkaskincare` |

Rules:

- All 6 domains resolve to the same EC2 Elastic IP (Cloudflare DNS-only, `proxied = false`, `ttl = 60`).
- Replace `<alias>` with the value of `ECR_PUBLIC_ALIAS`.
