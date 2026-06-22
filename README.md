# OPCUAtor

Maly serwis REST dzialajacy jak bezglowy klient OPC UA. Domyslnie startuje na porcie `9500` i potrafi pobrac drzewo obiektow z dowolnego serwera OPC UA, a nastepnie oddac je jako JSON.

## Instalacja

Fedora:

```bash
sudo dnf install -y python3 python3-pip python3-virtualenv jq
python3 -m venv .opcuator-venv
source .opcuator-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Konfiguracja

Skopiuj `.env.example` do `.env` i ustaw przynajmniej:

```ini
OPCUA_ENDPOINT=opc.tcp://adres-serwera:4840
```

Jesli serwer wymaga certyfikatow, mozna uzyc certyfikatow klienta podobnych do tych z UaExpert. Najprostszy wariant to ustawienie:

```ini
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/opcuator-client.pem,certs/opcuator-client-key.pem
```

Jesli serwer wymaga metody security `None`, ustaw:

```ini
OPCUA_SECURITY_STRING=None
```

To jest rownowazne pustemu `OPCUA_SECURITY_STRING=`, ale czytelniejsze przy przepisywaniu ustawien z dokumentacji.

Niektore serwery embedded zwracaja pusta liste `UserIdentityTokens`, mimo ze przyjmuja sesje Anonymous. OPCUAtor domyslnie probuje obejsc ten przypadek:

```ini
OPCUA_ASSUME_ANONYMOUS_IF_NO_TOKENS=true
```

Pliki certyfikatow moga byc skopiowane z profilu UaExpert albo wygenerowane osobno. Serwer OPC UA musi zaufac certyfikatowi klienta, tak samo jak przy UaExpert.

## Certyfikat klienta OPC UA

### Uzycie certyfikatu z UaExpert

Jesli serwer ma juz zaufac certyfikatowi z UaExpert, skopiuj z profilu UaExpert:

- `PKI/own/certs/uaexpert.der` do `certs/uaexpert.der`,
- `PKI/own/private/uaexpert_key.pem` do `certs/uaexpert_key.pem`.

Potem sprawdz certyfikat i odczytaj `Application URI` oraz hash SHA256:

```bash
python scripts/inspect-opcua-cert.py certs/uaexpert.der
```

Hash z pola `SHA256 hex` powinien byc ta sama wartoscia, ktora wpisujesz po stronie serwera do whitelisty certyfikatow klienta. W `.env` ustaw:

```ini
OPCUA_ENDPOINT=opc.tcp://OR2HPM-EH9-9999-023:4840/OPCUA/LithosServer
OPCUA_APPLICATION_URI=wartosc_z_Application_URI_z_certyfikatu
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
OPCUA_USERNAME=
OPCUA_PASSWORD=
```

Jesli hostname z endpointu nie rozwiazuje sie na Fedorze, dodaj wpis do `/etc/hosts`, np.:

```bash
sudo sh -c 'echo "10.243.71.16 OR2HPM-EH9-9999-023" >> /etc/hosts'
```

### Wygenerowanie certyfikatu w stylu UaExpert

OPCUAtor moze wygenerowac wlasny certyfikat klienta w takim samym ukladzie plikow jak UaExpert:

```bash
source .opcuator-venv/bin/activate
python scripts/generate-opcua-client-cert.py
```

Powstana pliki:

- `certs/uaexpert_key.pem` - prywatny klucz klienta, zostaje lokalnie,
- `certs/uaexpert.der` - publiczny certyfikat klienta w formacie DER dla OPCUAtor i do zaufania po stronie serwera.

Do `.env` wpisz:

```ini
OPCUA_APPLICATION_NAME=OPCUAtor
OPCUA_APPLICATION_URI=wartosc_Application_URI_wypisana_przez_generator
OPCUA_PRODUCT_URI=urn:opcuator:client
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/uaexpert.der,certs/uaexpert_key.pem
```

Wartosc `OPCUA_APPLICATION_URI` powinna byc taka sama jak `Application URI` wypisane przez generator.

Publiczny certyfikat DER skopiuj do katalogu zaufanych certyfikatow klientow na serwerze OPC UA:

```bash
scp certs/uaexpert.der USER@HOST:/home/bmterra/lithos/security/opcua/trusted/
```

Jesli katalog wymaga uprawnien administracyjnych, skopiuj najpierw do `/tmp`, a potem przenies na serwerze:

```bash
scp certs/uaexpert.der USER@HOST:/tmp/
ssh USER@HOST 'sudo cp /tmp/uaexpert.der /home/bmterra/lithos/security/opcua/trusted/'
```

Klucz prywatny `certs/uaexpert_key.pem` nie powinien byc kopiowany na serwer ani commitowany do repozytorium.

Jesli potrzebna jest dodatkowa kopia certyfikatu w PEM, uzyj:

```bash
python scripts/generate-opcua-client-cert.py --write-pem-cert
```

## Uruchomienie

Linux / Fedora:

```bash
chmod +x opcuator.sh
./opcuator.sh
```

Serwis bedzie dostepny pod:

- `GET http://localhost:9500/health`
- `GET http://localhost:9500/config`
- `GET http://localhost:9500/endpoints`
- `GET http://localhost:9500/namespace`
- `POST http://localhost:9500/browse`

## Przyklady

Pobranie standardowego folderu `Objects`:

```bash
curl "http://localhost:9500/namespace?max_depth=8&max_nodes=5000" | jq .
```

Sprawdzenie profili bezpieczenstwa udostepnianych przez serwer:

```bash
curl "http://localhost:9500/endpoints" | jq .
```

Jesli `/endpoints` pokazuje `server_application_uri`, a polaczenie albo browse nadal jest odrzucane, mozna skopiowac te wartosc do `.env`:

```ini
OPCUA_SERVER_URI=wartosc_z_pola_server_application_uri
```

Nie nalezy mylic tego z `OPCUA_APPLICATION_URI`: `OPCUA_APPLICATION_URI`, `OPCUA_APPLICATION_NAME` i `OPCUA_PRODUCT_URI` opisuja klienta OPCUAtor, a `OPCUA_SERVER_URI` opisuje aplikacje serwera.

Jesli serwer jest wrazliwy na duze zapytania browse, mozna zmniejszyc liczbe referencji pobieranych naraz:

```ini
OPCUA_BROWSE_REFERENCES_PER_NODE=100
```

Pobranie z endpointem podanym w zapytaniu:

```bash
curl "http://localhost:9500/namespace?endpoint=opc.tcp://192.168.1.50:4840&max_depth=6" | jq .
```

Wariant `POST`, wygodny do testow:

```bash
curl -X POST "http://localhost:9500/browse" \
  -H "Content-Type: application/json" \
  -d '{"endpoint":"opc.tcp://192.168.1.50:4840","root_node":"i=85","max_depth":8,"max_nodes":5000}' \
  | jq .
```

## Co jest w JSON

Odpowiedz zawiera:

- `namespace_array`: indeksy namespace z serwera OPC UA,
- `tree`: drzewo obiektow od wskazanego `root_node`,
- dla kazdego wezla: `node_id`, `browse_name`, `display_name`, `description`, `node_class`, `children`,
- opcjonalnie aktualne wartosci zmiennych, gdy ustawisz `include_values=true`,
- widoczne metody OPC UA, gdy serwer pokazuje je jako wezly klasy `Method`.

## Opcjonalnie: usluga systemd

Przyklad pliku `/etc/systemd/system/opcuator.service`:

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

Po skopiowaniu projektu do `/opt/opcuator`:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now opcuator
sudo systemctl status opcuator
```

## Opcjonalnie: synchronizacja z GitHub

Najprostsza konfiguracja na Fedorze:

```bash
chmod +x scripts/setup-github-sync.sh scripts/opcuator-github-sync.sh
scripts/setup-github-sync.sh
```

Domyslnie skrypt uzywa repozytorium:

```text
git@github.com:wstalsprzedkompa/OPCUAtor.git
```

Mozna tez jawnie podac adres HTTPS:

```bash
scripts/setup-github-sync.sh https://github.com/wstalsprzedkompa/OPCUAtor.git main
```

Do automatycznej synchronizacji co 5 minut:

```bash
sudo mkdir -p /etc/opcuator
sudo cp systemd/opcuator-github-sync.env.example /etc/opcuator/github-sync.env
sudo cp systemd/opcuator-github-sync.service /etc/systemd/system/
sudo cp systemd/opcuator-github-sync.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now opcuator-github-sync.timer
sudo systemctl list-timers opcuator-github-sync.timer
```

Skrypt synchronizacji robi `pull --rebase --autostash`, dodaje zmiany z katalogu projektu, tworzy commit, jesli cos sie zmienilo, i wysyla branch `main` do `origin`. Plik `.env` oraz lokalne venv sa ignorowane przez `.gitignore`, wiec sekrety i zaleznosci nie powinny trafic do repozytorium.

Do automatycznego pushowania najlepiej skonfigurowac klucz SSH dla konta/uzytkownika, pod ktorym dziala timer:

```bash
ssh -T git@github.com
```
