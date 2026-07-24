# Disconnected environments

> [!WARNING]
> Veritas is designed to run on a trusted, connected machine or bastion
> host — outside the cluster being attested. Running it inside the
> workload cluster compromises the security model: a compromised cluster
> could manipulate the computed reference values, which would then be
> trusted by Trustee.

> [!NOTE]
> The flags below are optional. In most cases veritas pulls directly
> from public registries and no extra configuration is needed. If your
> environment does not have access to public registries, these options
> allow you to point veritas at a local mirror instead.

## Registry mirror

Use `--mirror-registry` to redirect image pulls to a local mirror.
The mirror must preserve the original image path structure, as
produced by `oc-mirror`:

```bash
# Azure
veritas --platform azure --tee snp \
  --mirror-registry my-acr.azurecr.io \
  --authfile pull-secret.json

# Baremetal
veritas --platform baremetal --tee tdx --ocp-version 4.20.15 \
  --mirror-registry my-acr.azurecr.io \
  --authfile pull-secret.json
```

## Image signature verification

By default veritas downloads the Red Hat cosign public key from
`security.access.redhat.com` and verifies signatures against the Red
Hat Rekor transparency log. In disconnected environments:

- Use `--cosign-pub-key` to provide the cosign public key as a local
  PEM file, eliminating the download.
- Use `--skip-tlog` to skip the Rekor transparency log check. The
  cosign signature is still verified against the public key.
- Use `--rekor-url` and `--rekor-pub-key-url` to point to a local
  Rekor instance if one is available.

Full disconnected example for Azure:

```bash
veritas --platform azure --tee snp \
  --mirror-registry my-acr.azurecr.io \
  --authfile pull-secret.json \
  --cosign-pub-key /path/to/cosign.pub \
  --skip-tlog
```
