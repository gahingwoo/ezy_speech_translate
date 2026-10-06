#!/usr/bin/env bash
# EzySpeech installer and manager.
#
#   curl -fsSL https://github.com/gahingwoo/ezy_speech_translate/releases/latest/download/install.sh | sudo bash
#
# Asks how to install it, then installs the latest release:
#   Docker   in a container, settings in a Docker volume
#   Native   as two system services run by an "ezyspeech" account, on Linux
#            with systemd, settings in /var/lib/ezyspeech
# Run again on a machine that has it, it is the place to update, restart,
# change the admin password, read the log, back up, or uninstall.
#
# Options (all optional; with --yes nothing is asked):
#   --docker | --native        how to install
#   --port N  --admin-port N   listener page (1915) and console (1916)
#   --https                    self-signed HTTPS, so the console's microphone
#                              works from another computer
#   --external-url URL         public address, when a tunnel or proxy is in front
#   --version V                a particular release instead of the latest
#   --source PATH              install from a package file or a copy of the code
#   --cockpit | --no-cockpit   the Cockpit management module (if Cockpit is there)
#   --yes                      take the defaults, ask nothing
#   --lang en|zh               the language of these screens
#
# Copyright (C) 2025-2026 Ga Hing Woo (Jiaxing Hu)
# This file is part of EzySpeech, and is free software under the GNU Affero
# General Public License, version 3 or later. See LICENSE and TRADEMARK.md.

# Everything is in main(), called on the last line: a download cut short runs nothing.
main() {
set -uo pipefail

REPO="gahingwoo/ezy_speech_translate"
API="${EZY_RELEASE_API:-https://api.github.com/repos/$REPO/releases}"
TITLE="EzySpeech"

MODE=""; PORT=1915; ADMIN_PORT=1916; HTTPS=""; EXTERNAL_URL=""; WANT_VERSION=""
SOURCE=""; COCKPIT=""; ASSUME_YES=""; UI_LANG=""; MANAGE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --docker) MODE=docker ;;
        --native) MODE=native ;;
        --port) PORT="$2"; shift ;;
        --admin-port) ADMIN_PORT="$2"; shift ;;
        --https) HTTPS=self-signed ;;
        --no-https) HTTPS=off ;;
        --external-url) EXTERNAL_URL="$2"; shift ;;
        --version) WANT_VERSION="${2#v}"; shift ;;
        --source) SOURCE="$2"; shift ;;
        --cockpit) COCKPIT=yes ;;
        --no-cockpit) COCKPIT=no ;;
        --yes|-y) ASSUME_YES=1 ;;
        --lang) UI_LANG="$2"; shift ;;
        --manage) MANAGE=1 ;;
        -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]:-/dev/null}" 2>/dev/null || echo "See the top of install.sh"; return 0 ;;
        *) echo "Unknown option: $1 (try --help)" >&2; return 2 ;;
    esac
    shift
done
case "${UI_LANG:-${LC_ALL:-${LANG:-}}}" in zh*|*_CN*|*_TW*|*_HK*) UI_LANG=zh ;; *) UI_LANG=en ;; esac

OS="$(uname -s)"
IS_ROOT=0; [ "$(id -u)" = 0 ] && IS_ROOT=1
pick_ui

# Already installed: this is the manager.
if command -v ezyspeech >/dev/null 2>&1 && ezyspeech version >/dev/null 2>&1; then
    manage_menu
    return $?
fi
if [ -n "$MANAGE" ]; then
    die "$(L "EzySpeech is not installed on this machine." "这台机器还没有安装 EzySpeech。")"
fi
install_flow
}

# ── language ─────────────────────────────────────────────────────────────────
L() { if [ "$UI_LANG" = zh ]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

# ── the screens: whiptail, dialog, or plain prompts ──────────────────────────
pick_ui() {
    UI=plain
    if [ -z "$ASSUME_YES" ] && { : </dev/tty; } 2>/dev/null; then
        if command -v whiptail >/dev/null 2>&1; then UI=whiptail
        elif command -v dialog >/dev/null 2>&1; then UI=dialog
        fi
    fi
}
interactive() { [ -z "$ASSUME_YES" ] && { : </dev/tty; } 2>/dev/null; }

msg() {   # msg TEXT
    case "$UI" in
        whiptail|dialog) "$UI" --title "$TITLE" --msgbox "$1" 22 76 </dev/tty >/dev/tty 2>&1 ;;
        *) printf '\n%s\n' "$1" ;;
    esac
}

yesno() { # yesno TEXT DEFAULT(y|n)
    if ! interactive; then [ "$2" = y ]; return; fi
    case "$UI" in
        whiptail|dialog)
            local def=""; [ "$2" = n ] && def="--defaultno"
            "$UI" --title "$TITLE" $def --yesno "$1" 14 72 </dev/tty >/dev/tty 2>&1 ;;
        *)
            local hint="[y/N]" reply; [ "$2" = y ] && hint="[Y/n]"
            printf '%s %s ' "$1" "$hint" >/dev/tty; read -r reply </dev/tty || reply=""
            reply="${reply:-$2}"; [[ "$reply" =~ ^[Yy] ]] ;;
    esac
}

ask() {   # ask TEXT DEFAULT  -> prints the answer
    if ! interactive; then printf '%s' "$2"; return; fi
    case "$UI" in
        whiptail|dialog) "$UI" --title "$TITLE" --inputbox "$1" 10 72 "$2" 3>&1 1>&2 2>&3 </dev/tty ;;
        *) local reply; printf '%s [%s] ' "$1" "$2" >/dev/tty; read -r reply </dev/tty || reply=""; printf '%s' "${reply:-$2}" ;;
    esac
}

secret() { # secret TEXT -> prints what was typed
    case "$UI" in
        whiptail|dialog) "$UI" --title "$TITLE" --passwordbox "$1" 10 72 3>&1 1>&2 2>&3 </dev/tty ;;
        *) local reply; printf '%s ' "$1" >/dev/tty; stty -echo </dev/tty; read -r reply </dev/tty; stty echo </dev/tty; echo >/dev/tty; printf '%s' "$reply" ;;
    esac
}

choose() { # choose TEXT DEFAULT tag1 label1 tag2 label2 ... -> prints the tag
    local text="$1" def="$2"; shift 2
    if ! interactive; then printf '%s' "$def"; return; fi
    case "$UI" in
        whiptail|dialog)
            "$UI" --title "$TITLE" --default-item "$def" --menu "$text" 20 76 8 "$@" 3>&1 1>&2 2>&3 </dev/tty ;;
        *)
            local i=1 tags=() reply
            printf '\n%s\n' "$text" >/dev/tty
            while [ $# -gt 0 ]; do tags+=("$1"); printf '  %d) %s\n' "$i" "$2" >/dev/tty; i=$((i + 1)); shift 2; done
            printf '> ' >/dev/tty; read -r reply </dev/tty || reply=""
            if [[ "$reply" =~ ^[0-9]+$ ]] && [ "$reply" -ge 1 ] && [ "$reply" -le "${#tags[@]}" ]; then
                printf '%s' "${tags[$((reply - 1))]}"
            else printf '%s' "$def"; fi ;;
    esac
}

gauge() { # gauge TEXT  (reads "PROGRESS n text" lines on stdin)
    local line pct txt
    case "$UI" in
        whiptail|dialog)
            while IFS= read -r line; do
                case "$line" in
                    PROGRESS\ *) pct="${line#PROGRESS }"; txt="${pct#* }"; pct="${pct%% *}"
                                 printf 'XXX\n%s\n%s\nXXX\n' "$pct" "$txt" ;;
                esac
            done | "$UI" --title "$TITLE" --gauge "$1" 8 72 0 </dev/tty >/dev/tty 2>&1 ;;
        *)
            while IFS= read -r line; do
                case "$line" in PROGRESS\ *) pct="${line#PROGRESS }"; printf '  [%3s%%] %s\n' "${pct%% *}" "${pct#* }" ;; esac
            done ;;
    esac
}

die() { msg "$(L "Error" "出错了"): $1"; exit 1; }

as_root() {
    if [ "$IS_ROOT" = 1 ]; then "$@"
    elif command -v sudo >/dev/null 2>&1; then sudo "$@"
    else die "$(L "This step needs root, and sudo is not available." "这一步需要 root 权限，但没有 sudo。")"
    fi
}

# ── what the machine has ─────────────────────────────────────────────────────
has_systemd() { [ "$OS" = Linux ] && command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; }
has_docker()  { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }
has_cockpit() { [ -d /usr/share/cockpit ] || command -v cockpit-bridge >/dev/null 2>&1; }

lan_ip() {
    local ip="" iface
    if [ "$OS" = Darwin ]; then
        iface="$(route -n get default 2>/dev/null | awk '/interface:/ {print $2}')"
        [ -n "$iface" ] && ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    else
        ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
        [ -z "$ip" ] && ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    fi
    printf '%s' "${ip:-localhost}"
}

host_tz() {
    local tz=""
    command -v timedatectl >/dev/null 2>&1 && tz="$(timedatectl show -p Timezone --value 2>/dev/null || true)"
    [ -z "$tz" ] && [ -L /etc/localtime ] && tz="$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')"
    printf '%s' "$tz"
}

ensure_python() {
    command -v python3 >/dev/null 2>&1 && return
    [ "$OS" = Linux ] || die "$(L "Python 3 is needed. Install it and run this again." "需要 Python 3，请安装后重试。")"
    if command -v apt-get >/dev/null 2>&1; then as_root apt-get update -qq && as_root apt-get install -y -qq python3
    elif command -v dnf >/dev/null 2>&1; then as_root dnf install -y -q python3
    else die "$(L "Python 3 is needed." "需要 Python 3。")"; fi
}

sha256_of() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

# ── getting a release ────────────────────────────────────────────────────────
# Sets PKG (the package file) and VERSION, checked against SHA256SUMS.
fetch_release() {
    WORK="$(mktemp -d)"
    if [ -n "$SOURCE" ]; then
        PKG="$SOURCE"
        if [ -d "$SOURCE" ]; then VERSION="$(cat "$SOURCE/VERSION")"
        else VERSION="$(tar -xzOf "$SOURCE" --wildcards '*/VERSION' 2>/dev/null | head -1)"; fi
        COCKPIT_PKG="${EZY_COCKPIT_PKG:-}"
        return
    fi
    local url="$API/latest"
    [ -n "$WANT_VERSION" ] && url="$API/tags/v$WANT_VERSION"
    curl -fsSL -H 'Accept: application/vnd.github+json' "$url" -o "$WORK/release.json" \
        || die "$(L "Could not reach the release list on GitHub." "无法连接 GitHub 获取版本列表。")"
    eval "$(python3 - "$WORK/release.json" <<'PY'
import json, sys, shlex
d = json.load(open(sys.argv[1]))
v = str(d.get('tag_name', '')).lstrip('v')
a = {x['name']: x['browser_download_url'] for x in d.get('assets', [])}
print('VERSION=' + shlex.quote(v))
print('PKG_URL=' + shlex.quote(a.get(f'ezyspeech-{v}.tar.gz', '')))
print('SUMS_URL=' + shlex.quote(a.get('SHA256SUMS', '')))
print('COCKPIT_URL=' + shlex.quote(a.get(f'ezyspeech-cockpit-{v}.tar.gz', '')))
PY
)"
    [ -n "$PKG_URL" ] && [ -n "$SUMS_URL" ] || die "$(L "That release has no package to install." "这个版本没有可安装的包。")"
    curl -fsSL "$SUMS_URL" -o "$WORK/SHA256SUMS" && curl -fsSL "$PKG_URL" -o "$WORK/ezyspeech-$VERSION.tar.gz" \
        || die "$(L "The download failed." "下载失败。")"
    PKG="$WORK/ezyspeech-$VERSION.tar.gz"
    local want; want="$(awk -v f="ezyspeech-$VERSION.tar.gz" '$2 == f || $2 == "*"f {print $1}' "$WORK/SHA256SUMS")"
    [ -n "$want" ] && [ "$want" = "$(sha256_of "$PKG")" ] \
        || die "$(L "The package does not match its published SHA-256. Nothing was installed." "安装包与发布的 SHA-256 不符，已停止安装。")"
    COCKPIT_PKG=""
    if [ -n "$COCKPIT_URL" ]; then
        curl -fsSL "$COCKPIT_URL" -o "$WORK/cockpit.tar.gz" \
            && [ "$(awk -v f="ezyspeech-cockpit-$VERSION.tar.gz" '$2 == f {print $1}' "$WORK/SHA256SUMS")" = "$(sha256_of "$WORK/cockpit.tar.gz")" ] \
            && COCKPIT_PKG="$WORK/cockpit.tar.gz"
    fi
}

ezyspeech_tool() {  # the ezyspeech command from the package being installed
    if [ -d "$PKG" ]; then printf '%s' "$PKG/ops/ezyspeech"; return; fi
    mkdir -p "$WORK/tool" && tar -xzf "$PKG" -C "$WORK/tool" --strip-components 1
    printf '%s' "$WORK/tool/ops/ezyspeech"
}

# ── installing ───────────────────────────────────────────────────────────────
install_flow() {
    msg "$(L "Welcome. This installs EzySpeech, live speech translation for a room.

It asks a few questions, then downloads the latest release from GitHub, checks it, and installs it." \
"欢迎。这会安装 EzySpeech——给现场的实时语音翻译。

接下来问几个问题，然后从 GitHub 下载最新版本、校验并安装。")"

    # How
    local can_native=0; has_systemd && can_native=1
    if [ -z "$MODE" ]; then
        if [ "$can_native" = 1 ]; then
            MODE="$(choose "$(L "How should it be installed?" "选择安装方式：")" docker \
                docker "$(L "Docker   — in a container; simplest to remove" "Docker  —— 装在容器里，最容易卸载")" \
                native "$(L "Native   — system services under an 'ezyspeech' account" "原生    —— 系统服务，用 ezyspeech 账户运行")")" || exit 1
        else
            MODE=docker
        fi
    fi
    if [ "$MODE" = native ] && [ "$can_native" = 0 ]; then
        die "$(L "A native install needs Linux with systemd. Use Docker here." "原生安装需要带 systemd 的 Linux，这里请用 Docker。")"
    fi
    if [ "$MODE" = native ] && [ "$IS_ROOT" = 0 ]; then
        die "$(L "A native install needs root: run it with sudo." "原生安装需要 root：请用 sudo 运行。")"
    fi
    if [ "$MODE" = docker ] && ! has_docker; then
        if [ "$OS" = Linux ] && yesno "$(L "Docker is not installed. Install it now with Docker's own script (get.docker.com)?" "还没有 Docker。现在用 Docker 官方脚本（get.docker.com）安装？")" y; then
            curl -fsSL https://get.docker.com | as_root sh >/dev/null 2>&1 || die "$(L "Installing Docker failed." "Docker 安装失败。")"
            as_root systemctl enable --now docker >/dev/null 2>&1 || true
        else
            die "$(L "Docker is needed. On a Mac, install OrbStack or Docker Desktop and start it." "需要 Docker。Mac 上请安装并启动 OrbStack 或 Docker Desktop。")"
        fi
    fi

    # An install made by the old ezy_manager.py
    MIGRATE=""
    if [ "$MODE" = native ] && [ -d /opt/ezy_speech_translate/config ]; then
        if yesno "$(L "An earlier EzySpeech install is in /opt/ezy_speech_translate. Bring its settings, password and transcripts over?" "在 /opt/ezy_speech_translate 发现旧版安装。要把它的设置、密码和记录迁移过来吗？")" y; then
            MIGRATE=/opt/ezy_speech_translate
        fi
    fi

    # Ports and HTTPS
    PORT="$(ask "$(L "Port for the listener page:" "听众页面端口：")" "$PORT")" || exit 1
    ADMIN_PORT="$(ask "$(L "Port for the operator's console:" "操作台端口：")" "$ADMIN_PORT")" || exit 1
    if [ -z "$HTTPS" ] && [ -z "$EXTERNAL_URL" ]; then
        local h
        h="$(choose "$(L "Browsers allow the microphone only over HTTPS, or on the machine itself. Where will the console be opened?" "浏览器只在 HTTPS 或本机上允许用麦克风。操作台会在哪里打开？")" off \
            off "$(L "On this machine (plain HTTP)" "就在这台机器上（普通 HTTP）")" \
            self-signed "$(L "On another computer (self-signed HTTPS)" "在另一台电脑上（自签名 HTTPS）")" \
            external "$(L "Behind my own domain / tunnel" "通过我自己的域名/隧道")")" || exit 1
        case "$h" in
            external) HTTPS=off; EXTERNAL_URL="$(ask "$(L "The public address (https://...):" "公开地址（https://...）：")" "https://")" || exit 1 ;;
            *) HTTPS="$h" ;;
        esac
    fi

    # The admin password
    ADMIN_PASSWORD=""
    if interactive && ! yesno "$(L "Make a strong admin password for you? (No: type your own)" "要自动生成一个强管理员密码吗？（否：自己输入）")" y; then
        while :; do
            ADMIN_PASSWORD="$(secret "$(L "Admin password (8 or more characters):" "管理员密码（至少 8 位）：")")" || exit 1
            [ "${#ADMIN_PASSWORD}" -ge 8 ] && [ "$ADMIN_PASSWORD" = "$(secret "$(L "Again:" "再输一次：")")" ] && break
            msg "$(L "Too short, or they did not match. Try again." "太短或两次不一致，请重试。")"
        done
    fi

    # Cockpit
    if [ -z "$COCKPIT" ] && [ "$OS" = Linux ] && [ "$IS_ROOT" = 1 ]; then
        if has_cockpit; then
            yesno "$(L "Cockpit is on this machine. Add the EzySpeech module to it (status, updates, logs in the browser)?" "这台机器有 Cockpit。要加装 EzySpeech 管理模块吗（在浏览器里看状态、更新、日志）？")" y && COCKPIT=yes || COCKPIT=no
        else
            COCKPIT=no
        fi
    fi

    local summary
    summary="$(L "Ready to install:" "准备安装：")
  $(L "Mode" "方式"):           $MODE
  $(L "Listener page" "听众页面"):  port $PORT
  $(L "Console" "操作台"):        port $ADMIN_PORT
  HTTPS:          ${EXTERNAL_URL:-$HTTPS}
  Cockpit:        ${COCKPIT:-no}${MIGRATE:+
  $(L "Bring over" "迁移自"):     $MIGRATE}"
    yesno "$summary" y || exit 0

    ensure_python
    fetch_release
    local tool args log result
    tool="$(ezyspeech_tool)"
    args=(install --mode "$MODE" --source "$PKG" --port "$PORT" --admin-port "$ADMIN_PORT" --progress --tz "$(host_tz)")
    [ -n "$HTTPS" ] && args+=(--https "$HTTPS")
    [ "$HTTPS" = self-signed ] && args+=(--hostnames "$(lan_ip),$(hostname 2>/dev/null)")
    [ -n "$EXTERNAL_URL" ] && args+=(--external-url "$EXTERNAL_URL")
    [ "$COCKPIT" = yes ] && [ -n "${COCKPIT_PKG:-}" ] && args+=(--cockpit "$COCKPIT_PKG")
    [ -n "$MIGRATE" ] && args+=(--migrate-from "$MIGRATE")
    log="$WORK/install.log"
    EZY_ADMIN_PASSWORD="$ADMIN_PASSWORD" python3 "$tool" "${args[@]}" 2>&1 | tee "$log" \
        | gauge "$(L "Installing EzySpeech $VERSION..." "正在安装 EzySpeech $VERSION……")"
    local code=${PIPESTATUS[0]}
    if [ "$code" != 0 ]; then
        cp "$log" "/tmp/ezyspeech-install.log" 2>/dev/null || true
        die "$(grep '^FAILED' "$log" | tail -1 | cut -c8-)

$(L "The full log is in /tmp/ezyspeech-install.log." "完整日志在 /tmp/ezyspeech-install.log。")"
    fi
    result="$(grep '^RESULT ' "$log" | tail -1 | cut -c8-)"
    show_result "$result"
    rm -rf "$WORK"
}

show_result() {
    local ip pass scheme cockpit_line="" pw_line
    ip="$(lan_ip)"
    pass="$(printf '%s' "$1" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("password") or "")')"
    scheme=http; [ "$HTTPS" = self-signed ] && scheme=https
    [ "$COCKPIT" = yes ] && cockpit_line="
  Cockpit:        https://$ip:9090  → EzySpeech"
    if [ -n "$pass" ]; then pw_line="$pass
  $(L "Write it down: it is not shown again." "请记下：不会再显示。")"
    elif [ -n "${ADMIN_PASSWORD:-}" ]; then pw_line="$(L "(the one you typed)" "（你刚输入的那个）")"
    else pw_line="$(L "(kept from the earlier install)" "（沿用旧安装的密码）")"; fi
    msg "$(L "EzySpeech $VERSION is running." "EzySpeech $VERSION 已在运行。")

  $(L "Listeners" "听众"):      ${EXTERNAL_URL:-$scheme://$ip:$PORT}
  $(L "Projection" "投影"):     $scheme://$ip:$PORT/projection
  $(L "Console" "操作台"):        $scheme://$ip:$ADMIN_PORT
  $(L "Sign in as" "登录名"):     admin
  $(L "Password" "密码"):       $pw_line$cockpit_line

$(L "To manage it later (update, restart, password, logs):" "以后管理（更新、重启、改密码、日志）：")
  sudo ezyspeech status | update | restart | password | logs
  $(L "or run this installer again for the menu." "或再次运行本安装器打开菜单。")"
}

# ── managing ─────────────────────────────────────────────────────────────────
manage_menu() {
    local sudo_cmd=""; [ "$IS_ROOT" = 1 ] || sudo_cmd="sudo"
    while :; do
        local installed latest choice
        installed="$(ezyspeech version 2>/dev/null)"
        latest="$(ezyspeech check-update --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["latest"] + (" *" if d["update_available"] else ""))' 2>/dev/null || echo "?")"
        if ! interactive; then ezyspeech status; return 0; fi
        choice="$(choose "$(L "EzySpeech $installed is installed. Latest release: $latest" "已安装 EzySpeech $installed。最新版本：$latest")" status \
            status "$(L "Status" "运行状态")" \
            update "$(L "Update to the latest release" "更新到最新版本")" \
            restart "$(L "Restart" "重启")" \
            password "$(L "Set a new admin password" "重设管理员密码")" \
            logs "$(L "Recent log" "最近日志")" \
            backup "$(L "Back up settings and transcripts" "备份设置和记录")" \
            uninstall "$(L "Uninstall" "卸载")" \
            quit "$(L "Quit" "退出")")" || return 0
        case "$choice" in
            status)   msg "$(ezyspeech status 2>&1)" ;;
            update)   $sudo_cmd ezyspeech update --yes --progress 2>&1 | tee /tmp/ezyspeech-update.log | gauge "$(L "Updating..." "正在更新……")"
                      msg "$(grep -E '^(FAILED|PROGRESS 100)|up to date' /tmp/ezyspeech-update.log | tail -1 | sed 's/^PROGRESS 100 //; s/^FAILED /✗ /')" ;;
            restart)  $sudo_cmd ezyspeech restart && msg "$(L "Restarted." "已重启。")" ;;
            password) msg "$($sudo_cmd ezyspeech password --generate 2>&1)" ;;
            logs)     $sudo_cmd ezyspeech logs -n 60 >/tmp/ezyspeech-log.txt 2>&1
                      if [ "$UI" = plain ]; then cat /tmp/ezyspeech-log.txt; else "$UI" --title "$TITLE" --textbox /tmp/ezyspeech-log.txt 24 100 </dev/tty >/dev/tty 2>&1; fi ;;
            backup)   msg "$(cd "$HOME" && $sudo_cmd ezyspeech backup 2>&1)" ;;
            uninstall)
                      if yesno "$(L "Uninstall EzySpeech? Settings and transcripts are kept unless you also choose to delete them." "卸载 EzySpeech？除非接下来选择删除，设置和记录会保留。")" n; then
                          if yesno "$(L "Also DELETE its settings, password and transcripts?" "同时删除设置、密码和所有记录？")" n; then
                              $sudo_cmd ezyspeech uninstall --yes --purge
                          else
                              $sudo_cmd ezyspeech uninstall --yes
                          fi
                          msg "$(L "Uninstalled." "已卸载。")"; return 0
                      fi ;;
            *) return 0 ;;
        esac
    done
}

main "$@"
