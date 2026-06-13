# Image Signing Verification

Date: 2026-06-12
Audience: release managers and customer platform teams

Safe4AI release images are signed after they are pushed to GHCR. The signature
uses GitHub Actions OIDC through cosign keyless signing.

## Images

Release tags publish and sign:

```text
ghcr.io/<org>/<repo>/safe4ai-backend:<version>
ghcr.io/<org>/<repo>/safe4ai-frontend:<version>
```

Only immutable version tags are supported for customer deployment. Do not use
`latest`.

## Verification

Customers should verify signatures before promoting images:

```bash
cosign verify \
  --certificate-identity-regexp 'https://github.com/.+/.github/workflows/release.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/<org>/<repo>/safe4ai-backend:<version>

cosign verify \
  --certificate-identity-regexp 'https://github.com/.+/.github/workflows/release.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/<org>/<repo>/safe4ai-frontend:<version>
```

## Release evidence packet

Verify the signature together with:

- SPDX SBOMs for both images.
- Trivy SARIF reports for both images.
- Dependency/license reports for backend and frontend.
- GitHub release notes for the same version tag.

If a customer registry requires a different signing mechanism, document the
registry-specific verification command in the customer deployment addendum.
