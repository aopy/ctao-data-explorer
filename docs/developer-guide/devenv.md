# Development Environment Setup

This guide provides instructions for setting up a development environment for the CTAO Data Explorer project.

## Prerequisites

`docker` or `podman` installed on your machine.

## Setting Up the Development Environment

Kubernetes development environment can be setup using `aiv-toolkit`. Internally, it uses `kind` to create a local Kubernetes cluster.

Clone the repository:

   ```bash
   git clone https://gitlab.obspm.fr/oates/ctao-data-explorer.git   
   cd ctao-data-explorer
   git submodule update --init --recursive
   ```

Start the development environment:

   ```bash
   make install-chart
   ```

You should be able to see pods running:

   ```bash
   $ kubectl get pods
    NAME                                                       READY   STATUS      RESTARTS   AGE
    ctao-data-explorer-1c9a840-backend-65788b98f5-92nrq        1/1     Running     0          173m
    ctao-data-explorer-1c9a840-frontend-94b7f7fdf-6smfm        1/1     Running     0          101m
    ctao-data-explorer-1c9a840-postgresql-0                    1/1     Running     0          173m
    ctao-data-explorer-1c9a840-redis-master-7b4dc48d75-n7vbc   1/1     Running     0          173m
    testkit-5498b8cbf6-vc2gt                                   1/1     Running     0          174m
    toolkit-fluent-bit-cw8qp                                   1/1     Running     0          174m
    toolkit-wait-for-fluent-bit-79lmv                          0/1     Completed   0          174m
   ```

By the default, the cluster does not export any ports to the host machine. To access the frontend, you can use port forwarding:

   ```bash
   kubectl port-forward svc/ctao-data-explorer-1c9a840-frontend 3000:3000
   ```

Then open your browser at `http://localhost:3000`.

To start interactive shell inside a test pod:

   ```bash
   aiv-deploy helm-dev
   ```


## Adding playwright tests

To add Playwright tests to the project, follow these steps the instructions in the [Playwright documentation](https://playwright.dev/python/docs/codegen).