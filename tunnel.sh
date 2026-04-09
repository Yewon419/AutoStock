#!/usr/bin/env bash
# AutoStock — Cloudflare 터널 스크립트
# 외부/모바일 접속용. 종료 시 frontend/.env.local 자동 삭제.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_LOCAL="$SCRIPT_DIR/frontend/.env.local"
TUNNEL_LOG=$(mktemp)
TUNNEL_PID=""

cleanup() {
  echo ""
  echo "터널 종료 중..."
  [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null || true
  rm -f "$ENV_LOCAL" "$TUNNEL_LOG"
  echo ".env.local 삭제 완료 — 이제 localhost:8001로 연결됩니다."
}
trap cleanup EXIT INT TERM

echo "Cloudflare 터널 시작 중 (backend → :8001)..."
cloudflared tunnel --url http://localhost:8001 2>"$TUNNEL_LOG" &
TUNNEL_PID=$!

# 터널 URL이 로그에 나타날 때까지 최대 30초 대기
TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
  [[ -n "$TUNNEL_URL" ]] && break
  sleep 1
done

if [[ -z "$TUNNEL_URL" ]]; then
  echo "ERROR: 터널 URL 감지 실패. 로그:"
  cat "$TUNNEL_LOG"
  exit 1
fi

# .env.local 자동 생성
cat > "$ENV_LOCAL" << EOF
# 자동 생성 by tunnel.sh — 종료 시 자동 삭제됩니다. 수동으로 편집하지 마세요.
VITE_API_URL=${TUNNEL_URL}/api/v1
EOF

echo ""
echo "========================================="
echo "  외부 접속 준비 완료"
echo "  Backend : ${TUNNEL_URL}/api/v1"
echo "  Frontend: http://localhost:3001 (npm run dev -- --host --port 3001)"
echo "========================================="
echo ""
echo "Ctrl+C 로 터널 종료 (.env.local 자동 초기화)"

wait "$TUNNEL_PID"
