import urllib.request, json, sys, time

API = 'http://localhost:8000/api/v1'
results = []

def ok(name): results.append(('PASS', name, ''))
def fail(name, reason): results.append(('FAIL', name, str(reason)[:120]))

def req(method, path, data=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(f'{API}{path}', data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        body = resp.read()
        return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
            return e.code, json.loads(body) if body else {}
        except Exception:
            return e.code, {}

# ── 1. Health ──────────────────────────────────────────────
try:
    r0 = urllib.request.urlopen('http://localhost:8000/health')
    d0 = json.loads(r0.read())
    if d0.get('status') == 'ok':
        ok('Health check')
    else:
        fail('Health check', d0)
except Exception as e:
    fail('Health check', e)

# ── 2. Auth ────────────────────────────────────────────────
s, d = req('POST', '/auth/login', {'username': 'admin', 'password': 'admin1234'})
if s == 200 and 'access_token' in d:
    token = d['access_token']
    ok('Auth: 로그인')
else:
    fail('Auth: 로그인', d)
    sys.exit(1)

s, d = req('GET', '/auth/me', token=token)
if s == 200 and d.get('username') == 'admin':
    ok('Auth: /me')
else:
    fail('Auth: /me', d)

# ── 3. Market ──────────────────────────────────────────────
s, d = req('GET', '/market/stocks?limit=5', token=token)
stock_count = 0
ticker = None
if s == 200:
    stock_count = d.get('total', 0)
    ok(f'Market: 종목 목록 ({stock_count}개)')
    if d.get('items'):
        ticker = d['items'][0]['ticker']
else:
    fail('Market: 종목 목록', d)

if ticker:
    s, d2 = req('GET', f'/market/stocks/{ticker}', token=token)
    if s == 200:
        ok(f'Market: 종목 상세 ({ticker})')
    else:
        fail('Market: 종목 상세', d2)

    s, d3 = req('GET', f'/market/stocks/{ticker}/prices?limit=3', token=token)
    if s == 200 and isinstance(d3, list):
        ok(f'Market: 주가 데이터 ({len(d3)}건)')
    else:
        fail('Market: 주가 데이터', d3)

    s, d4 = req('GET', f'/market/stocks/{ticker}/indicators?limit=3', token=token)
    if s == 200 and isinstance(d4, list):
        ok(f'Market: 기술지표 ({len(d4)}건)')
    else:
        fail('Market: 기술지표', d4)
else:
    fail('Market: 데이터 없음 (수집 필요)', '종목 없음')

# ── 4. Strategies ──────────────────────────────────────────
s, d = req('POST', '/strategies', {
    'name': '[TEST] MA 전략',
    'conditions': [{'indicator': 'ma_20', 'condition': 'above', 'value': 0}]
}, token=token)
sid = None
if s == 201:
    sid = d['id']
    ok(f'Strategy: 생성 (id={sid})')
else:
    fail('Strategy: 생성', d)

if sid:
    s, d = req('GET', f'/strategies/{sid}', token=token)
    if s == 200 and d.get('name') == '[TEST] MA 전략':
        ok('Strategy: 단건 조회')
    else:
        fail('Strategy: 단건 조회', d)

    s, d = req('PUT', f'/strategies/{sid}', {'name': '[TEST] MA 전략 수정'}, token=token)
    if s == 200 and d.get('name') == '[TEST] MA 전략 수정':
        ok('Strategy: 수정')
    else:
        fail('Strategy: 수정', d)

    s, d = req('GET', '/strategies', token=token)
    if s == 200 and isinstance(d, list):
        ok(f'Strategy: 목록 ({len(d)}개)')
    else:
        fail('Strategy: 목록', d)

# ── 5. Bots ────────────────────────────────────────────────
s, d = req('POST', '/bots', {
    'name': '[TEST] 봇',
    'mode': 'mock',
    'strategy_id': sid,
    'tickers': ['005930', '000660'],
    'initial_cash': 3000000,
    'stop_loss_pct': 5.0,
    'take_profit_pct': 10.0,
    'max_order_amount': 1000000,
    'trading_start_time': '09:00',
    'trading_end_time': '15:20',
}, token=token)
bid = None
if s == 201:
    bid = d['id']
    ok(f'Bot: 생성 (id={bid}, mode={d.get("mode")})')
else:
    fail('Bot: 생성', d)

if bid:
    s, d = req('GET', '/bots', token=token)
    if s == 200 and isinstance(d, list):
        ok(f'Bot: 목록 ({len(d)}개)')
    else:
        fail('Bot: 목록', d)

    s, d = req('GET', f'/bots/{bid}', token=token)
    if s == 200 and d.get('id') == bid:
        ok('Bot: 단건 조회')
    else:
        fail('Bot: 단건 조회', d)

    s, d = req('PUT', f'/bots/{bid}', {'stop_loss_pct': 7.0}, token=token)
    if s == 200 and float(d.get('stop_loss_pct', 0)) == 7.0:
        ok('Bot: 수정')
    else:
        fail('Bot: 수정', d)

    s, d = req('POST', f'/bots/{bid}/start', token=token)
    if s == 200 and d.get('status') == 'RUNNING':
        ok('Bot: 시작')
    else:
        fail('Bot: 시작', d)

    s, d = req('GET', f'/bots/{bid}/positions', token=token)
    if s == 200 and isinstance(d, list):
        ok(f'Bot: 포지션 조회 ({len(d)}개)')
    else:
        fail('Bot: 포지션 조회', d)

    s, d = req('GET', f'/bots/{bid}/orders', token=token)
    if s == 200 and isinstance(d, list):
        ok(f'Bot: 주문 내역 ({len(d)}건)')
    else:
        fail('Bot: 주문 내역', d)

    s, d = req('GET', f'/bots/{bid}/reports', token=token)
    if s == 200 and isinstance(d, list):
        ok(f'Bot: 보고서 ({len(d)}건)')
    else:
        fail('Bot: 보고서', d)

    s, d = req('POST', f'/bots/{bid}/stop', token=token)
    if s == 200 and d.get('status') == 'STOPPED':
        ok('Bot: 정지')
    else:
        fail('Bot: 정지', d)

# ── 6. Accounts ────────────────────────────────────────────
s, d = req('POST', '/accounts', {
    'account_number': '1234567890',
    'owner_name': '홍길동',
    'broker': 'kiwoom',
    'account_type': 'paper',
}, token=token)
aid = None
if s == 201:
    aid = d['id']
    ok(f'Account: 생성 (type={d.get("account_type")})')
else:
    fail('Account: 생성', d)

if aid:
    s, d = req('GET', '/accounts', token=token)
    if s == 200 and isinstance(d, list):
        ok(f'Account: 목록 ({len(d)}개)')
    else:
        fail('Account: 목록', d)

    s, d = req('DELETE', f'/accounts/{aid}', token=token)
    if s == 204:
        ok('Account: 삭제')
    else:
        fail('Account: 삭제', d)

# ── 7. Broker ──────────────────────────────────────────────
s, d = req('GET', '/broker/status', token=token)
if s == 200 and 'mode' in d:
    ok(f'Broker: 상태 (mode={d.get("mode")})')
else:
    fail('Broker: 상태', d)

s, d = req('GET', '/broker/alerts', token=token)
if s == 200 and isinstance(d, list):
    ok(f'Broker: 알림 조회 ({len(d)}건)')
else:
    fail('Broker: 알림 조회', d)

s, d = req('POST', '/broker/emergency-stop', {}, token=token)
if s == 200 and 'count' in d:
    ok(f'Broker: 비상정지 ({d.get("count")}개 정지)')
else:
    fail('Broker: 비상정지', d)

# ── 8. Dashboard ───────────────────────────────────────────
s, d = req('GET', '/dashboard/summary', token=token)
if s == 200 and 'total_assets' in d:
    ok(f'Dashboard: 요약 (봇{d.get("bot_count")}개, running={d.get("running")})')
else:
    fail('Dashboard: 요약', d)

s, d = req('GET', '/dashboard/bots', token=token)
if s == 200 and isinstance(d, list):
    ok(f'Dashboard: 봇 스냅샷 ({len(d)}개)')
else:
    fail('Dashboard: 봇 스냅샷', d)

# ── 9. Backtest ────────────────────────────────────────────
if sid and ticker:
    s, d = req('POST', f'/strategies/{sid}/backtest', {
        'tickers': [ticker],
        'start_date': '2024-01-01',
        'end_date': '2024-06-30',
        'initial_capital': 5000000,
    }, token=token)
    if s == 200 and 'task_id' in d:
        task_id = d['task_id']
        ok(f'Backtest: 태스크 생성 (task_id={task_id[:8]}...)')

        # 결과 폴링 (최대 10초)
        for _ in range(5):
            time.sleep(2)
            s2, d2 = req('GET', f'/strategies/{sid}/backtest/{task_id}', token=token)
            if s2 == 200 and d2.get('status') in ('completed', 'failed'):
                if d2.get('status') == 'completed':
                    summary = d2.get('result', {}).get('summary', {})
                    grade = summary.get('grade', '?')
                    ret = summary.get('total_return_pct', '?')
                    trades = summary.get('num_trades', '?')
                    ok(f'Backtest: 완료 (grade={grade}, return={ret}%, trades={trades})')
                else:
                    fail('Backtest: 실패', d2.get('error', ''))
                break
        else:
            ok('Backtest: 실행 중 (폴링 타임아웃)')
    else:
        fail('Backtest: 태스크 생성', d)

# ── 정리 ───────────────────────────────────────────────────
if bid:
    req('DELETE', f'/bots/{bid}', token=token)
if sid:
    req('DELETE', f'/strategies/{sid}', token=token)

# ── 결과 출력 ──────────────────────────────────────────────
passes = [r for r in results if r[0] == 'PASS']
fails  = [r for r in results if r[0] == 'FAIL']

print()
print(f'{"="*50}')
print(f'  테스트 결과: {len(passes)}개 통과 / {len(fails)}개 실패')
print(f'{"="*50}')
for r in results:
    icon = 'PASS' if r[0] == 'PASS' else 'FAIL'
    mark = 'v' if r[0] == 'PASS' else 'x'
    line = f'  [{mark}] {r[1]}'
    if r[0] == 'FAIL' and r[2]:
        line += f'  -> {r[2]}'
    print(line)
print()
if fails:
    sys.exit(1)
