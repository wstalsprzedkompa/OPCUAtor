# OPCUAtor

OPCUAtor is an OPC UA client with a REST API. It listens on port `9500` by default and can expose an OPC UA server address space as JSON.

## Quick Start on Fedora

Run these commands in a freshly cloned repository:

```bash
sudo dnf install -y python3 python3-pip python3-virtualenv jq
python3 -m venv .opcuator-venv
source .opcuator-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Then choose one certificate setup:

- Copy an existing UaExpert certificate:

```bash
mkdir -p certs
cp /path/to/UaExpert/PKI/own/certs/uaexpert.der certs/uaexpert.der
cp /path/to/UaExpert/PKI/own/private/uaexpert_key.pem certs/uaexpert_key.pem
python scripts/inspect-opcua-cert.py certs/uaexpert.der
```

- Or generate a UaExpert-style certificate with OPCUAtor:

```bash
python scripts/generate-opcua-client-cert.py
```

Both paths produce/use:

- `certs/uaexpert.der`
- `certs/uaexpert_key.pem`

Use the printed `SHA256 hex` value in the server-side client certificate whitelist, and copy the printed `Application URI` to `.env` as `OPCUA_APPLICATION_URI`.

After editing `.env`, start OPCUAtor:

```bash
chmod +x opcuator.sh
./opcuator.sh
```

On startup, OPCUAtor prints its name, REST port, and ready-to-use URLs.
Set `NO_COLOR=1` before starting it if you want to disable colored terminal output.

## Basic `.env`

Set the OPC UA endpoint:

```ini
OPCUA_ENDPOINT=opc.tcp://server-host:4840/OPCUA/Server
```

If the endpoint hostname does not resolve on Fedora, add it to `/etc/hosts`:

```bash
sudo sh -c 'echo "192.0.2.10 server-host" >> /etc/hosts'
```

For a secure endpoint using a UaExpert-style certificate:

```ini
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
OPCUA_USERNAME=
OPCUA_PASSWORD=
```

For a server using security method `None`:

```ini
OPCUA_SECURITY_STRING=None
```

Some embedded servers return an empty `UserIdentityTokens` list even though they accept Anonymous sessions. OPCUAtor can try Anonymous anyway:

```ini
OPCUA_ASSUME_ANONYMOUS_IF_NO_TOKENS=true
```

If `/endpoints` returns `server_application_uri` and connection or browsing is rejected, copy that value to `.env`:

```ini
OPCUA_SERVER_URI=value_from_server_application_uri
```

Do not confuse this with `OPCUA_APPLICATION_URI`: `OPCUA_APPLICATION_URI`, `OPCUA_APPLICATION_NAME`, and `OPCUA_PRODUCT_URI` describe the OPCUAtor client. `OPCUA_SERVER_URI` describes the server application.

## Using a UaExpert Certificate

Use this path when UaExpert already works and the server whitelist contains the UaExpert certificate hash.

Copy these files from the UaExpert profile:

- `PKI/own/certs/uaexpert.der` to `certs/uaexpert.der`
- `PKI/own/private/uaexpert_key.pem` to `certs/uaexpert_key.pem`

Inspect the certificate:

```bash
source .opcuator-venv/bin/activate
python scripts/inspect-opcua-cert.py certs/uaexpert.der
```

The output contains:

- `SHA256 hex`: use this value in the server-side client certificate whitelist.
- `Application URI`: set this exact value as `OPCUA_APPLICATION_URI`.

Example `.env` values:

```ini
OPCUA_ENDPOINT=opc.tcp://server-host:4840/OPCUA/Server
OPCUA_APPLICATION_URI=application_uri_from_the_certificate
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
OPCUA_USERNAME=
OPCUA_PASSWORD=
```

## Generating a UaExpert-Style Certificate

Use this path when you do not want to generate the client certificate in UaExpert.

Generate the files:

```bash
source .opcuator-venv/bin/activate
python scripts/generate-opcua-client-cert.py
```

Generated files:

- `certs/uaexpert_key.pem` - private client key, keep it local.
- `certs/uaexpert.der` - public DER client certificate for OPCUAtor and the server trust/whitelist setup.

The generator prints:

- `SHA256 hex`: use this value in the server-side client certificate whitelist.
- `Application URI`: set this exact value as `OPCUA_APPLICATION_URI`.

Example `.env` values:

```ini
OPCUA_ENDPOINT=opc.tcp://server-host:4840/OPCUA/Server
OPCUA_APPLICATION_NAME=OPCUAtor
OPCUA_APPLICATION_URI=application_uri_printed_by_the_generator
OPCUA_PRODUCT_URI=urn:opcuator:client
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
```

If the server also requires a trusted certificate file, copy only the public DER certificate:

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

## REST Endpoints

Available endpoints:

- `GET http://localhost:9500/health`
- `GET http://localhost:9500/config`
- `GET http://localhost:9500/endpoints`
- `GET http://localhost:9500/namespace`
- `POST http://localhost:9500/browse`

Check server endpoint/security information:

```bash
curl "http://localhost:9500/endpoints" | jq .
```

Browse the standard `Objects` folder:

```bash
curl "http://localhost:9500/namespace?max_depth=8&max_nodes=5000" | jq .
```

If the server is sensitive to large browse requests, reduce the number of references requested at once in `.env`:

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
