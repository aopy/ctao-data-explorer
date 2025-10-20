# CI/CD for Docs

## GitLab Pages

1. Add a **`requirements-docs.txt`**:

```
mkdocs-material
pymdown-extensions
```

2. Add or extend **`.gitlab-ci.yml`**:

```yaml
stages: [build, deploy]

build:docs:
  image: python:3.12
  stage: build
  before_script:
    - pip install -r requirements-docs.txt
  script:
    - mkdocs build --strict --site-dir public
  artifacts:
    paths: [public]
  only:
    - main
    - master

pages:
  stage: deploy
  dependencies: [build:docs]
  script: []
  artifacts:
    paths: [public]
  only:
    - main
    - master
```

Site will be published under **GitLab Pages** (project Settings → Pages).

## Alternatives

- **Read the Docs** (supports MkDocs and Sphinx) for versioned docs
- **GitHub Pages** for the mirror repository
- **CTAO central docs**: if/when a shared developer portal exists, mirror or aggregate selected pages there
