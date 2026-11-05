#!/usr/bin/env bash
# Preparazione di un server Ubuntu 24.04 per GERVA Capital. Da eseguire UNA volta, come root, subito dopo la creazione.
#   curl -O .../server_setup.sh && less server_setup.sh && sudo bash server_setup.sh
# Prerequisito: la tua chiave SSH pubblica e' gia' in /root/.ssh/authorized_keys (la mette il provider alla creazione).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "eseguire come root"; exit 1; }
[ -s /root/.ssh/authorized_keys ] || { echo "manca /root/.ssh/authorized_keys: senza chiave ti chiuderesti fuori"; exit 1; }
USER_NAME="${USER_NAME:-gerva}"

export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get -y upgrade
apt-get install -y --no-install-recommends ca-certificates curl gnupg git ufw fail2ban unattended-upgrades sqlite3 age chrony

# --- utente di servizio con la stessa chiave SSH di root
id "$USER_NAME" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$USER_NAME"
usermod -aG sudo "$USER_NAME"
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "/home/$USER_NAME/.ssh"
install -m 600 -o "$USER_NAME" -g "$USER_NAME" /root/.ssh/authorized_keys "/home/$USER_NAME/.ssh/authorized_keys"
echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$USER_NAME" && chmod 440 "/etc/sudoers.d/90-$USER_NAME"

# --- SSH: solo chiavi, niente root, solo l'utente di servizio, tunnel locali ammessi (portale e VNC)
# 00-: sshd tiene il PRIMO valore letto, quindi questo file vince su 50-cloud-init.conf (PasswordAuthentication yes)
cat > /etc/ssh/sshd_config.d/00-gerva.conf <<CONF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers $USER_NAME
MaxAuthTries 3
LoginGraceTime 20
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding local
PermitTunnel no
ClientAliveInterval 300
CONF
sshd -t
for kv in "passwordauthentication no" "permitrootlogin no" "kbdinteractiveauthentication no"; do
  sshd -T | grep -qx "$kv" || { echo "sshd: '$kv' non applicato, controlla /etc/ssh/sshd_config.d/"; exit 1; }
done
systemctl restart ssh

# --- firewall: entra solo SSH. ATTENZIONE: Docker scavalca ufw per le porte PUBBLICATE; per questo il compose
#     pubblica solo su 127.0.0.1 e mai su 0.0.0.0.
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp
ufw --force enable

# --- fail2ban su SSH
cat > /etc/fail2ban/jail.d/sshd.local <<CONF
[sshd]
enabled = true
maxretry = 4
bantime = 1h
findtime = 10m
CONF
systemctl enable --now fail2ban

# --- aggiornamenti di sicurezza automatici, riavvio alle 04:30 se serve (fuori dagli orari di GERVA-Q)
cat > /etc/apt/apt.conf.d/52gerva-unattended <<CONF
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
CONF
dpkg-reconfigure -f noninteractive unattended-upgrades

# --- orologio: il server in UTC (i container usano Europe/Rome), sincronizzato
timedatectl set-timezone UTC
systemctl enable --now chrony

# --- Docker dal repository ufficiale
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
cat > /etc/docker/daemon.json <<CONF
{ "log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"},
  "no-new-privileges": true, "live-restore": true, "userland-proxy": false, "icc": false }
CONF
systemctl restart docker
usermod -aG docker "$USER_NAME"

# --- cartelle
install -d -m 750 -o "$USER_NAME" -g "$USER_NAME" /srv/gerva /srv/gerva/backups
echo
echo "Fatto. Prossimi passi (come $USER_NAME, da una NUOVA sessione SSH prima di chiudere questa):"
echo "  ssh $USER_NAME@<server>   # verifica che entri con la chiave"
echo "  cd /srv/gerva && git clone https://github.com/Andrea-Gervasoni/GERVA-Capital && copia GERVA-Q in /srv/gerva/GERVA-Q"
echo "  poi segui GERVA-Capital/docs/DEPLOY.md"
