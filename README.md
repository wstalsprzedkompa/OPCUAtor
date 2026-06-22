# OPCUAtor

OPCUAtor is an OPC UA client with a REST API. It listens on port `9500` by default and can expose an OPC UA server address space as JSON.

## Installation

Fedora:

```bash
sudo dnf install -y python3 python3-pip python3-virtualenv jq
python3 -m venv .opcuator-venv
source .opcuator-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set at least:

```ini
OPCUA_ENDPOINT=opc.tcp://server-host:4840/OPCUA/Server
```

If the server requires certificates, use:

```ini
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
```

If the server uses security method `None`, set:

```ini
OPCUA_SECURITY_STRING=None
```

This is equivalent to an empty `OPCUA_SECURITY_STRING=`, but it is clearer when copying settings from documentation.

Some embedded servers return an empty `UserIdentityTokens` list even though they accept Anonymous sessions. OPCUAtor can try Anonymous anyway:

```ini
OPCUA_ASSUME_ANONYMOUS_IF_NO_TOKENS=true
```

## OPC UA Client Certificate

### Using a UaExpert Certificate

If the server already trusts a UaExpert client certificate, copy these files from the UaExpert profile:

- `PKI/own/certs/uaexpert.der` to `certs/uaexpert.der`
- `PKI/own/private/uaexpert_key.pem` to `certs/uaexpert_key.pem`

Inspect the certificate and read its `Application URI` and SHA256 hash:

```bash
python scripts/inspect-opcua-cert.py certs/uaexpert.der
```

The `SHA256 hex` value is the value to put into the server-side client certificate whitelist. In `.env`, set:

```ini
OPCUA_ENDPOINT=opc.tcp://server-host:4840/OPCUA/Server
OPCUA_APPLICATION_URI=application_uri_from_the_certificate
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
OPCUA_USERNAME=
OPCUA_PASSWORD=
```

If the endpoint hostname does not resolve on Fedora, add it to `/etc/hosts`:

```bash
sudo sh -c 'echo "192.0.2.10 server-host" >> /etc/hosts'
```

### Generating a UaExpert-Style Certificate

OPCUAtor can generate a client certificate using the same file layout as UaExpert:

```bash
source .opcuator-venv/bin/activate
python scripts/generate-opcua-client-cert.py
```

Generated files:

- `certs/uaexpert_key.pem` - private client key, keep it local
- `certs/uaexpert.der` - public DER client certificate for OPCUAtor and the server trust/whitelist setup

In `.env`, set:

```ini
OPCUA_APPLICATION_NAME=OPCUAtor
OPCUA_APPLICATION_URI=application_uri_printed_by_the_generator
OPCUA_PRODUCT_URI=urn:opcuator:client
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
```

`OPCUA_APPLICATION_URI` must match the `Application URI` printed by the generator.

Copy the public DER certificate to the OPC UA server trust directory if the server requires a trusted certificate file:

```bash
scp certs/uaexpert.der USER@HOST:/path/to/opcua/trusted/
```

If the directory requires administrative permissions, copy to `/tmp` first and move it on the server:

```bash
scp certs/uaexpert.der USER@HOST:/tmp/
ssh USER@HOST 'sudo cp /tmp/uaexpert.der /path/to/opcua/trusted/'
```

Do not copy the private key `certs/uaexpert_key.pem` to the server, and do not commit it to the repository.

If you also need a PEM copy of the certificate, run:

```bash
python scripts/generate-opcua-client-cert.py --write-pem-cert
```

## Running

Linux / Fedora:

```bash
chmod +x opcuator.sh
./opcuator.sh
```

On startup, OPCUAtor prints its name, REST port, and a few ready-to-use URLs.

Available REST endpoints:

- `GET http://localhost:9500/health`
- `GET http://localhost:9500/config`
- `GET http://localhost:9500/endpoints`
- `GET http://localhost:9500/namespace`
- `POST http://localhost:9500/browse`

## Examples

Browse the standard `Objects` folder:

```bash
curl "http://localhost:9500/namespace?max_depth=8&max_nodes=5000" | jq .
```

Check security profiles exposed by the OPC UA server:

```bash
curl "http://localhost:9500/endpoints" | jq .
```

If `/endpoints` returns `server_application_uri` and connection or browsing is rejected, copy that value to `.env`:

```ini
OPCUA_SERVER_URI=value_from_server_application_uri
```

Do not confuse this with `OPCUA_APPLICATION_URI`: `OPCUA_APPLICATION_URI`, `OPCUA_APPLICATION_NAME`, and `OPCUA_PRODUCT_URI` describe the OPCUAtor client. `OPCUA_SERVER_URI` describes the server application.

If the server is sensitive to large browse requests, reduce the number of references requested at once:

```ini
OPCUA_BROWSE_REFERENCES_PER_NODE=100
```

Browse with an endpoint passed in the request:

```bash
curl "http://localhost:9500/namespace?endpoint=opc.tcp://server-host:4840/OPCUA/Server&max_depth=6" | jq .
```

POST variant:

```bash
curl -X POST "http://localhost:9500/browse" \
  -H "Content-Type: application/json" \
  -d '{"endpoint":"opc.tcp://server-host:4840/OPCUA/Server","root_node":"i=85","max_depth":8,"max_nodes":5000}' \
  | jq .
```

## JSON Response

The browse response contains:

- `namespace_array`: namespace indexes returned by the OPC UA server
- `tree`: the object tree starting at `root_node`
- per node: `node_id`, `browse_name`, `display_name`, `description`, `node_class`, `children`
- optional variable values when `include_values=true`
- visible OPC UA methods when the server exposes nodes with class `Method`

## Optional systemd Service

Example `/etc/systemd/system/opcuator.service`:

```ini
[Unit]
Description=OPCUAtor OPC UA REST service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/opcuator
ExecStart=/opt/opcuator/opcuator.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

After copying the project to `/opt/opcuator`:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opcuator
sudo systemctl status opcuator
```

## Optional GitHub Sync

Initial setup on Fedora:

```bash
chmod +x scripts/setup-github-sync.sh scripts/opcuator-github-sync.sh
scripts/setup-github-sync.sh
```

The script uses this repository by default:

```text
git@github.com:wstalsprzedkompa/OPCUAtor.git
```

You can also pass the HTTPS URL explicitly:

```bash
scripts/setup-github-sync.sh https://github.com/wstalsprzedkompa/OPCUAtor.git main
```

Automatic sync every 5 minutes:

```bash
sudo mkdir -p /etc/opcuator
sudo cp systemd/opcuator-github-sync.env.example /etc/opcuator/github-sync.env
sudo cp systemd/opcuator-github-sync.service /etc/systemd/system/
sudo cp systemd/opcuator-github-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now opcuator-github-sync.timer
sudo systemctl list-timers opcuator-github-sync.timer
```

The sync script runs `pull --rebase --autostash`, adds project changes, creates a commit when needed, and pushes branch `main` to `origin`. `.env` and local virtual environments are ignored by `.gitignore`, so secrets and installed dependencies should not be committed.

For automatic pushes, configure SSH for the account or user running the timer:

```bash
ssh -T git@github.com
```
