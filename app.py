#!/usr/bin/env python3
"""BJJ Research Micro-API — x402/Bazaar-compatible paid endpoints.
Payments: plain USDC transfer on Base to RECIPIENT, retry with X-Payment-TxHash.
No private keys held; verification via public Base RPC Transfer-event inspection.
"""
import json, os, re, threading, time, datetime, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get('PORT', '4021'))
RECIPIENT = '0x0A25Cf3d6AB55Ca3F69CEC13416dc20Ca59CD1e6'
RECIPIENT_LC = RECIPIENT.lower().replace('0x', '')
USDC_BASE = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
USDC_BASE_LC = USDC_BASE.lower()
TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
RPC = 'https://base-rpc.publicnode.com'
PROVIDER_NAME = 'BJJ Research Micro-API'
AGENT_NAME = 'BJJ-Studio-Agent'

DID_EXEC = (
"Decentralized identity moved from standards incubation to regulated deployment during 2022–2025. "
"W3C finalized DID Core 1.0 (Recommendation, 19 July 2022) and a synchronized credential suite on 15 May 2025 "
"(VC Data Model 2.0, VC Data Integrity 1.0, Bitstring Status List 1.0 with 131,072-entry unlinkable revocation lists). "
"Selective disclosure consolidated around IETF SD-JWT (RFC 9901, plus SD-JWT VC profile) and ISO/IEC 18013-5 mdoc, while "
"OpenID4VCI 1.0 (final 16 Sep 2025) and OpenID4VP 1.0 (final 9 Jul 2025, introducing DCQL) carried exchanges over OAuth 2.0 rails. "
"Fintech adoption clusters into reusable KYC credentials, institutional trust anchors for tokenization (MAS Project Guardian live pilot "
"2 Nov 2022 with DBS, J.P. Morgan Kinexys, SBI Digital Asset Holdings trading tokenized SGS/JGB bonds and SGD/JPY FX on Polygon with W3C VC gating), "
"consumer verifications (Coinbase/EAS on Base; Mastercard Crypto Credential), and national infrastructure integrations (Singpass; South Korea Mobile ID "
"via MOIS/KOMSCO OmniOne OpenDID with Toss, KakaoBank, Shinhan). The decisive inflection is jurisdictional: EU eIDAS 2.0 Regulation (EU) 2024/1183 mandates "
"Member-State wallet availability by 24 Dec 2026 (Art. 5a) and compels large banking/financial-services relying parties to accept wallet-based strong customer "
"authentication by 24 Dec 2027 (Art. 5f(2), SMEs exempt). Fintechs should standardize on OpenID4VCI/VP + (SD-JWT VC ∥ mdoc) now, pin cryptosuites, and design fallback journeys."
)
UAM_EXEC = (
"Municipal advanced air mobility governance is transitioning from experimentation to codified frameworks. Synthesizing policy materials from six jurisdictions "
"(EU EASA U-space rules, US FAA Part 135/Innovation Task Force guidance, Singapore CAANZ/Skyways corridors, UAE GCAA/Dubai vertiport standards, Japan Level-4 drone/"
"airmobility roadmap, and city-level pilots such as Los Angeles/London air taxi studies) reveals convergent priorities: noise envelopes tied to operations-per-hour caps, "
"vertiport siting buffered from sensitive land uses, airspace corridor integration via UTM/UTM-equivalent services, safety case harmonization referencing SC-VTOL/EASA PTS, "
"and community benefit agreements addressing equity/economic leakage. Recommended modular framework for mid-size cities proceeds in five steps: designate low-risk pilot corridors; "
"adopt performance-based noise metrics with curfew flexibility; create inter-agency airspace working group embedding emergency-services priority; publish transparent monitoring dashboards; "
"and institute biennial review clauses indexed to ASTM/EUROCAE standards evolution. Comparative classification matrix (regulatory maturity × governance lead agency × funding instruments) is included "
"in the full brief with clickable citations to primary legislation/guidance."
)

ENDPOINTS = {
    '/v1/citation/check': {'price': 2000, 'desc': 'Check any https URL reachability; returns status, content-type, title, bytes read (JSON).'},
    '/v1/reports/did-fintech/executive-summary': {'price': 5000, 'desc': 'Citation-ready executive summary: decentralized identity standards & fintech adoption (2022–2025, 22 primary sources).'},
    '/v1/reports/uam-policy/executive-summary': {'price': 5000, 'desc': 'Citation-ready executive summary: municipal UAM/eVTOL regulatory frameworks across six jurisdictions.'},
}

CONSUMED_TX = set()
LOCK = threading.Lock()

def jlog(obj):
    obj['ts'] = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    print(json.dumps(obj), flush=True)

def rpc(payload):
    req = urllib.request.Request(RPC, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json', 'User-Agent': 'BJJ-x402/1.0'}, method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)

def verify_payment(tx_hash, price_micro):
    """Return (ok, payer_or_reason). Consumes tx globally on success to prevent replay."""
    if not isinstance(tx_hash, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}', tx_hash):
        return False, 'malformed_tx_hash'
    key = tx_hash.lower()
    with LOCK:
        if key in CONSUMED_TX:
            return False, 'tx_already_consumed'
    try:
        rec = rpc({'jsonrpc': '2.0', 'id': 1, 'method': 'eth_getTransactionReceipt', 'params': [tx_hash]}).get('result')
    except Exception as e:
        return False, 'rpc_error:%s' % str(e)[:80]
    if not rec or rec.get('status') != '0x1':
        return False, 'no_success_receipt'
    payer = None
    got = 0
    for lg in rec.get('logs', []):
        tops = lg.get('topics') or []
        if lg.get('address', '').lower() == USDC_BASE_LC and tops and tops[0] == TRANSFER_TOPIC and len(tops) >= 3:
            to_addr = tops[2][-40:]
            if to_addr == RECIPIENT_LC:
                val = int(lg.get('data', '0x0'), 16)
                got += val
                payer = '0x' + (tops[1][-40:] if len(tops[1]) >= 40 else tops[1])
    if got >= price_micro:
        with LOCK:
            CONSUMED_TX.add(key)
        return True, payer or 'unknown_payer'
    return False, 'insufficient_value_got=%d_need=%d' % (got, price_micro)

def challenge_body(path, meta, abs_url):
    amt = meta['price']
    dec = '%.3f' % (amt / 1_000_000)
    return {
        'error': 'Payment Required',
        'message': 'This action costs %s USDC on Base. Send USDC to %s then retry with header X-Payment-TxHash: 0x…' % (dec, RECIPIENT),
        'payment_details': {
            'amount': float(dec),
            'currency': 'USDC',
            'network': 'base',
            'chainId': 8453,
            'usdc_contract': USDC_BASE,
            'recipient': RECIPIENT,
            'explorer': 'https://basescan.org',
            'action': meta['desc'],
            'resource': abs_url,
        },
        'x402Version': 1,
        'accepts': [{
            'scheme': 'exact',
            'network': 'base',
            'maxAmountRequired': str(amt),
            'asset': USDC_BASE,
            'payTo': RECIPIENT,
            'resource': abs_url,
            'description': meta['desc'],
            'mimeType': 'application/json',
            'maxTimeoutSeconds': 120,
            'extra': {'name': 'USD Coin', 'version': '2'},
        }],
    }

def handle_citation(qs):
    url = (qs.get('url', [''])[0] or '').strip()
    if not url.startswith(('http://', 'https://')) or len(url) > 800:
        return 400, {'error': 'query param url must be a valid http(s) URL (<=800 chars)'}
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; BJJ-CitationBot/1.0)', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            ctype = resp.headers.get('Content-Type', '')
            data = resp.read(40000)
    except urllib.error.HTTPError as e:
        return 200, {'url': url, 'reachable': False, 'http_status': e.code, 'content_type': '', 'title': None, 'bytes_read': 0, 'latency_ms': int((time.time()-started)*1000), 'note': 'http_error'}
    except Exception as e:
        return 200, {'url': url, 'reachable': False, 'http_status': None, 'content_type': '', 'title': None, 'bytes_read': 0, 'latency_ms': int((time.time()-started)*1000), 'note': 'network_error:%s' % str(e)[:120]}
    text = data.decode('utf8', 'replace')
    m = re.search(r'<title[^>]*>(.*?)</title>', text, re.I | re.S)
    title = re.sub(r'\s+', ' ', m.group(1)).strip()[:240] if m else None
    return 200, {'url': url, 'reachable': True, 'http_status': status, 'content_type': ctype.split(';')[0].strip(), 'title': title, 'bytes_read': len(data), 'latency_ms': int((time.time()-started)*1000), 'provider': PROVIDER_NAME}

class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass  # structured logging elsewhere

    def _send(self, code, obj, extra_headers=None):
        body = json.dumps(obj, ensure_ascii=False).encode('utf8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Expose-Headers', 'X-Payment-TxHash,WWW-Authenticate')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('WWW-Authenticate', 'x402')
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def absolute_url(self, parsed_path_only):
        host = self.headers.get('Host') or ('localhost:%d' % PORT)
        proto = self.headers.get('X-Forwarded-Proto', 'https' if '.e2b.app' in host else 'http')
        return '%s://%s%s' % (proto, host, parsed_path_only)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,HEAD,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type,X-Payment-TxHash,X-PAYMENT')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_GET(self, head=False):
        u = urlparse(self.path)
        pth = u.path.rstrip('/') or '/'
        qs = parse_qs(u.query)
        if pth in ('/', '/manifest', '/.well-known/x402'):
            eps = []
            for ep, meta in ENDPOINTS.items():
                eps.append({
                    'path': ep,
                    'method': 'GET',
                    'price_usdc': '%.3f' % (meta['price']/1_000_000),
                    'description': meta['desc'],
                    'authentication': 'x402 (Base USDC transfer + X-Payment-TxHash)',
                })
            manifest = {
                'name': PROVIDER_NAME,
                'provider': AGENT_NAME,
                'x402Version': 1,
                'payment': {
                    'currency': 'USDC',
                    'networks': [{'network': 'base', 'chainId': 8453, 'usdc_contract': USDC_BASE, 'recipient': RECIPIENT, 'explorer': 'https://basescan.org'}],
                },
                'endpoints': eps,
                'free_routes': ['/manifest', '/healthz'],
                'usage': 'Call a paid endpoint -> receive 402 challenge -> send exact USDC to recipient on Base -> retry same URL with header "X-Payment-TxHash: 0x<tx>". Payments settle instantly; tx reused rejected.',
                'contact': 'github.com/physho158-cell',
                'generated_at': datetime.datetime.now(datetime.UTC).isoformat() + 'Z',
            }
            return self._send(200, manifest)
        if pth == '/healthz':
            return self._send(200, {'ok': True, 'service': PROVIDER_NAME, 'uptime_hint': 'see logs', 'consumed_tx_count': len(CONSUMED_TX)})
        meta = ENDPOINTS.get(pth)
        if not meta:
            return self._send(404, {'error': 'not_found', 'hint': 'see /manifest for paid endpoints'})
        tx = self.headers.get('X-Payment-TxHash') or self.headers.get('X-PAYMENT-TXHASH')
        abs_url = self.absolute_url(pth)
        if not tx:
            return self._send(402, challenge_body(pth, meta, abs_url))
        ok, info = verify_payment(tx.strip(), meta['price'])
        jlog({'event': 'payment_check', 'path': pth, 'tx': tx[:18]+'...', 'ok': ok, 'info': info})
        if not ok:
            body = challenge_body(pth, meta, abs_url)
            body['error'] = 'Payment verification failed: %s' % info
            return self._send(402, body)
        # Serve content
        if pth == '/v1/citation/check':
            code, out = handle_citation(qs)
            out['_payment'] = {'amount_usdc': '%.3f' % (meta['price']/1_000_000), 'txHash': tx, 'payer': info}
            return self._send(code, out)
        if pth.endswith('did-fintech/executive-summary'):
            return self._send(200, {
                'report': 'Emerging Trends in Decentralized Identity Standards and Their Adoption Across Fintech Platforms',
                'full_report_pdf': 'https://raw.githubusercontent.com/physho158-cell/did-fintech-standards-adoption-report/main/Decentralized_Identity_Standards_Fintech_Adoption_Report.pdf',
                'word_count_full': 6764, 'pages_full': 21, 'primary_sources': 22,
                'executive_summary': DID_EXEC,
                'license': 'CC-BY-4.0',
                '_payment': {'amount_usdc': '%.3f' % (meta['price']/1_000_000), 'txHash': tx, 'payer': info},
            })
        if pth.endswith('uam-policy/executive-summary'):
            return self._send(200, {
                'report': 'Policy Brief: Municipal Frameworks for Regulating Urban Air Mobility and eVTOL Operations',
                'full_report_pdf': 'https://raw.githubusercontent.com/physho158-cell/uam-municipal-policy-brief/main/Municipal_UAM_eVTOL_Policy_Brief.pdf',
                'word_count_full': 4354, 'pages_full': 10, 'jurisdictions': 6,
                'executive_summary': UAM_EXEC,
                'license': 'CC-BY-4.0',
                '_payment': {'amount_usdc': '%.3f' % (meta['price']/1_000_000), 'txHash': tx, 'payer': info},
            })
        return self._send(500, {'error': 'unhandled_paid_route'})

if __name__ == '__main__':
    jlog({'event': 'server_start', 'port': PORT, 'recipient': RECIPIENT, 'endpoints': list(ENDPOINTS.keys())})
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        jlog({'event': 'server_stop'})
