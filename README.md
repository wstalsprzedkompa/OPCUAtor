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
OPCUA_SECURITY_STRING=Basic256Sha256,SignAndEncrypt,certs/client_cert.pem,certs/client_key.pem,certs/server_cert.pem
```

Pliki certyfikatow moga byc skopiowane z profilu UaExpert albo wygenerowane osobno. Serwer OPC UA musi zaufac certyfikatowi klienta, tak samo jak przy UaExpert.

## Uruchomienie

Linux / Fedora:

```bash
chmod +x opcuator.sh
./opcuator.sh
```

Serwis bedzie dostepny pod:

- `GET http://localhost:9500/health`
- `GET http://localhost:9500/config`
- `GET http://localhost:9500/namespace`
- `POST http://localhost:9500/browse`

## Przyklady

Pobranie standardowego folderu `Objects`:

```bash
curl "http://localhost:9500/namespace?max_depth=8&max_nodes=5000" | jq .
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
