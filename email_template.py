"""
HTML Email Builder for Polymarket OSINT Monitor
Clean, styled digest that renders well in Gmail.
"""

def build_html_email(news, suspicious_markets, large_trades, onchain_txs,
                     uma, ofac, bills, win_alerts, weekly,
                     narrative, developing_stories, today_pretty):

    high   = [h for h in news if h.get("priority")]
    normal = [h for h in news if not h.get("priority")]
    is_quiet = (len(high) == 0 and len(suspicious_markets) == 0
                and len(large_trades) == 0 and len(onchain_txs) == 0
                and len(uma) == 0)

    def esc(s):
        return str(s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

    def badge(text, color):
        colors = {
            "red":    ("#ff5c5c","#2a1010"),
            "yellow": ("#ffb547","#2a1f00"),
            "teal":   ("#00c2aa","#002a25"),
            "blue":   ("#5b8dee","#0d1a33"),
            "green":  ("#42c97c","#0a2118"),
            "gray":   ("#8b91a8","#1e2030"),
        }
        fg, bg = colors.get(color, ("#8b91a8","#1e2030"))
        return f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;white-space:nowrap">{esc(text)}</span>'

    def stat_box(num, label, color):
        colors = {"red":"#ff5c5c","yellow":"#ffb547","teal":"#00c2aa","green":"#42c97c","gray":"#8b91a8"}
        c = colors.get(color,"#8b91a8")
        return f'''<td style="text-align:center;padding:16px;background:#1a1d27;border:1px solid #ffffff14;border-radius:8px;min-width:90px">
            <div style="font-size:28px;font-weight:700;color:{c};letter-spacing:-1px;line-height:1">{esc(str(num))}</div>
            <div style="font-size:10px;color:#5a6080;text-transform:uppercase;letter-spacing:0.8px;margin-top:4px">{esc(label)}</div>
        </td>'''

    def section_header(title, count=None):
        count_str = f' <span style="color:#5a6080;font-size:12px;font-weight:400">({count})</span>' if count is not None else ""
        return f'''<tr><td style="padding:20px 0 8px">
            <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;color:#5a6080;border-bottom:1px solid #ffffff14;padding-bottom:8px">
                {esc(title)}{count_str}
            </div>
        </td></tr>'''

    def news_row(item, show_priority=True):
        pri = badge("HIGH PRIORITY","red") + "&nbsp;" if (show_priority and item.get("priority")) else ""
        src = badge(item.get("source",""),"gray")
        also = ""
        if item.get("also_covered_by"):
            also = f'&nbsp;<span style="color:#5a6080;font-size:11px">+{len(item["also_covered_by"])} more</span>'
        wl = f'&nbsp;{badge("WATCHLIST","yellow")}' if item.get("watchlist_hit") else ""
        pub = f'<span style="color:#5a6080;font-size:11px">{esc(item.get("pub_date",""))}</span>'
        summary = f'<div style="color:#8b91a8;font-size:13px;line-height:1.5;margin:6px 0">{esc(item.get("summary",""))}</div>' if item.get("summary") and len(item.get("summary","")) > 20 else ""
        link = f'<a href="{esc(item.get("link",""))}" style="color:#00c2aa;font-size:12px;text-decoration:none">Read article ↗</a>' if item.get("link") else ""
        return f'''<tr><td style="padding:14px 0;border-bottom:1px solid #ffffff0a">
            <div style="margin-bottom:6px">{pri}{src}{also}{wl}&nbsp;&nbsp;{pub}</div>
            <div style="font-size:14px;font-weight:500;color:#f0f2f8;line-height:1.4;margin-bottom:4px">{esc(item.get("title",""))}</div>
            {summary}{link}
        </td></tr>'''

    def trade_row(market):
        risk = market.get("insider_risk","MEDIUM")
        risk_colors = {"HIGH":("#ff5c5c","#ff5c5c22"),"MEDIUM":("#ffb547","#ffb54722"),"LOW":("#5b8dee","#5b8dee22")}
        border_color, risk_bg = risk_colors.get(risk, ("#ffb547","#ffb54722"))
        risk_labels = {
            "HIGH": "HIGH EVENT-ACCESS CRITERIA",
            "MEDIUM": "MEDIUM REVIEW CRITERIA",
            "LOW": "LOW INFO-ASYMMETRY / WASH CHECK",
        }
        risk_badge = badge(risk_labels.get(risk, "REVIEW CRITERIA"), "red" if risk=="HIGH" else ("yellow" if risk=="MEDIUM" else "blue"))
        days = market.get("days_until_close", 9999)
        days_str = f"{days} days until close" if days < 9999 else "long-term"
        urgency_color = "#ff5c5c" if days <= 30 else ("#ffb547" if days <= 90 else "#5a6080")
        return f'''<tr><td style="padding:14px;background:#1a1d27;border-left:4px solid {border_color};border-radius:0 8px 8px 0;margin-bottom:8px;display:block">
            <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
                {risk_badge}
                <span style="font-size:11px;color:{urgency_color};font-weight:600">{esc(days_str)}</span>
            </div>
            <div style="font-size:15px;font-weight:600;color:#f0f2f8;margin-bottom:8px;line-height:1.3">{esc(market.get("question",""))}</div>
            <div style="display:flex;align-items:center;gap:16px;margin-bottom:8px">
                <span style="font-size:22px;font-weight:700;color:{border_color};letter-spacing:-0.5px">${"{:,.0f}".format(market.get("volume_usd",0))}</span>
                <span style="font-size:13px;color:#ffb547;font-weight:500">{esc(str(market.get("probability_pct",0)))}% probability &nbsp;·&nbsp; {esc(market.get("outcome",""))} outcome</span>
            </div>
            <div style="font-size:12px;color:#5a6080;margin-bottom:8px">Closes: {esc(market.get("end_date",""))} &nbsp;·&nbsp; Flagged: {esc(market.get("flagged_date",""))}</div>
            <div style="margin-top:6px;font-size:12px;color:{border_color};background:{risk_bg};padding:8px;border-radius:6px">{esc(market.get("alert_reason",""))}</div>
            <a href="{esc(market.get("url",""))}" style="color:#00c2aa;font-size:12px;text-decoration:none;display:inline-block;margin-top:8px">View on Polymarket ↗</a>
        </td></tr>'''

    def onchain_row(tx):
        wl = f'&nbsp;{badge("WATCHLIST","yellow")}' if tx.get("watchlist") else ""
        return f'''<tr><td style="padding:14px;background:#1a1d27;border-left:3px solid #5b8dee;border-radius:0 8px 8px 0;margin-bottom:8px;display:block">
            <div style="font-size:18px;font-weight:700;color:#5b8dee;margin-bottom:6px">${"{:,.2f}".format(tx.get("value_usdc",0))} USDC{wl}</div>
            <div style="font-size:11px;color:#5a6080;font-family:monospace;margin-bottom:3px">From: {esc(tx.get("from",""))}</div>
            <div style="font-size:11px;color:#5a6080;font-family:monospace;margin-bottom:3px">To: {esc(tx.get("to",""))}</div>
            <div style="font-size:11px;color:#5a6080;margin-bottom:8px">{esc(tx.get("timestamp",""))}</div>
            <a href="{esc(tx.get("polygonscan",""))}" style="color:#00c2aa;font-size:12px;text-decoration:none;margin-right:12px">View TX ↗</a>
            <a href="{esc(tx.get("from_link",""))}" style="color:#00c2aa;font-size:12px;text-decoration:none">Wallet profile ↗</a>
        </td></tr>'''

    def bill_row(b):
        return f'''<tr><td style="padding:12px 0;border-bottom:1px solid #ffffff0a">
            <table width="100%" cellpadding="0" cellspacing="0"><tr>
                <td style="vertical-align:top">
                    <a href="{esc(b.get("url",""))}" style="font-size:13px;font-weight:500;color:#00c2aa;text-decoration:none">{esc(b.get("bill",""))}</a>
                    <div style="font-size:11px;color:#5a6080;font-family:monospace;margin-top:2px">{esc(b.get("id",""))}</div>
                </td>
                <td style="text-align:right;vertical-align:top;max-width:260px;padding-left:12px">
                    <div style="font-size:12px;color:#8b91a8">{esc(b.get("latest_action",""))}</div>
                    <div style="font-size:11px;color:#5a6080;margin-top:2px">{esc(b.get("action_date",""))}</div>
                </td>
            </tr></table>
        </td></tr>'''

    def uma_row(a):
        type_color = "red" if a.get("alert_type") == "POLYMARKET DISPUTE" else "yellow"
        return f'''<tr><td style="padding:14px;background:#1a1d27;border-left:3px solid {"#ff5c5c" if type_color=="red" else "#ffb547"};border-radius:0 8px 8px 0;margin-bottom:8px;display:block">
            <div style="margin-bottom:6px">{badge(a.get("alert_type","DISPUTE"), type_color)}&nbsp;<span style="font-size:11px;color:#5a6080">{esc(a.get("published",""))}</span></div>
            <div style="font-size:13px;font-weight:500;color:#f0f2f8;margin-bottom:6px">{esc(a.get("title",""))}</div>
            <div style="font-size:12px;color:#8b91a8;margin-bottom:6px">{esc(a.get("summary",""))}</div>
            <div style="font-size:12px;color:#ffb547;margin-bottom:6px">⚠ {esc(a.get("note",""))}</div>
            <a href="{esc(a.get("link",""))}" style="color:#00c2aa;font-size:12px;text-decoration:none">View on UMA forum ↗</a>
        </td></tr>'''

    # Build sections
    suspicious_html = ""
    if suspicious_markets:
        suspicious_markets = sorted(suspicious_markets, key=lambda x: ({"HIGH":0,"MEDIUM":1,"LOW":2}.get(x.get("insider_risk","MEDIUM"),1), x.get("days_until_close",9999)))
        rows = "\n".join(f'<tr><td style="padding-bottom:8px">' + trade_row(m).replace("<tr>","").replace("</tr>","") + "</td></tr>" for m in suspicious_markets)
        suspicious_html = f'''
        {"".join(f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">{trade_row(m)}</table>' for m in suspicious_markets)}'''

    onchain_html = ""
    if onchain_txs:
        onchain_html = f'''
        {"".join(f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">{onchain_row(tx)}</table>' for tx in onchain_txs)}'''

    high_news_html = "".join(news_row(i, True) for i in high)
    normal_news_html = "".join(news_row(i, True) for i in normal)
    bills_html = "".join(bill_row(b) for b in bills)
    uma_html = "".join(f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">{uma_row(a)}</table>' for a in uma)

    developing_html = ""
    if developing_stories:
        items = ""
        for s in developing_stories[:3]:
            days = len(s.get("dates_seen",[]))
            items += f'''<div style="padding:10px;background:#1f2235;border-radius:6px;margin-bottom:6px">
                <span style="color:#ffb547;font-size:11px;font-weight:600">DAY {days}</span>
                <div style="font-size:13px;color:#f0f2f8;margin-top:3px">{esc(s.get("representative_title","")[:80])}</div>
                <div style="font-size:11px;color:#5a6080;margin-top:3px">Active since {esc(s.get("dates_seen",[""])[0])}</div>
            </div>'''
        developing_html = f'''
        <tr>{section_header("Developing Stories — Watch These")}</tr>
        <tr><td style="padding-bottom:16px">{items}</td></tr>'''

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Polymarket OSINT Digest</title></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1117;padding:20px 0">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%">

  <!-- HEADER -->
  <tr><td style="padding:24px 0 16px;border-bottom:1px solid #ffffff14">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <div style="font-size:18px;font-weight:600;color:#f0f2f8;letter-spacing:-0.3px">
          <span style="display:inline-block;width:8px;height:8px;background:#00c2aa;border-radius:50%;margin-right:8px;vertical-align:middle"></span>
          Polymarket OSINT Daily Digest
        </div>
        <div style="font-size:12px;color:#5a6080;margin-top:4px">{esc(today_pretty)} &nbsp;·&nbsp; Cleveland EDT</div>
      </td>
      <td align="right">
        <div style="font-size:11px;color:#5a6080;background:#1a1d27;border:1px solid #ffffff14;border-radius:6px;padding:6px 12px;white-space:nowrap">
          {"🔴 " + str(len(high)) + " HIGH PRIORITY" if high else ("✓ Quiet day" if is_quiet else str(len(news)) + " stories")}
        </div>
      </td>
    </tr></table>
  </td></tr>

  <!-- NARRATIVE SUMMARY -->
  <tr><td style="padding:20px 0 0">
    <div style="background:#1a1d27;border:1px solid #ffffff14;border-radius:10px;padding:16px">
      <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#00c2aa;margin-bottom:8px">Today's Intelligence Summary</div>
      <div style="font-size:13px;color:#c0c8e0;line-height:1.6">{esc(narrative)}</div>
    </div>
  </td></tr>

  <!-- STAT GRID -->
  <tr><td style="padding:16px 0">
    <table width="100%" cellpadding="4" cellspacing="4"><tr>
      {stat_box(len(high), "High Priority", "red")}
      {stat_box(len(suspicious_markets), "Review Markets", "red")}
      {stat_box(len(onchain_txs), "On-Chain Flags", "blue")}
      {stat_box(len(uma), "UMA Disputes", "yellow")}
      {stat_box(len(bills), "Bills Tracked", "green")}
      {stat_box(len(news), "News Stories", "gray")}
    </tr></table>
  </td></tr>

  <!-- DEVELOPING STORIES -->
  {developing_html}

  <!-- SUSPICIOUS MARKETS -->
  {"".join([f'<tr>{section_header("Market Review Criteria Matched", len(suspicious_markets))}</tr><tr><td style="padding-bottom:16px">' + suspicious_html + "</td></tr>"]) if suspicious_markets else ""}

  <!-- ON-CHAIN -->
  {"".join([f'<tr>{section_header("On-Chain Large Transactions (Polygon)", len(onchain_txs))}</tr><tr><td style="padding-bottom:16px">' + onchain_html + "</td></tr>"]) if onchain_txs else ""}

  <!-- UMA -->
  {"".join([f'<tr>{section_header("UMA Governance / Oracle Disputes", len(uma))}</tr><tr><td style="padding-bottom:16px">' + uma_html + "</td></tr>"]) if uma else ""}

  <!-- HIGH PRIORITY NEWS -->
  {"".join([f'<tr>{section_header("High Priority News", len(high))}</tr>' + high_news_html]) if high else ""}

  <!-- GENERAL NEWS -->
  {"".join([f'<tr>{section_header("General News & Regulatory Updates", len(normal))}</tr>' + normal_news_html]) if normal else ""}

  <!-- BILLS -->
  <tr>{section_header("Congressional Bill Tracker", len(bills))}</tr>
  <table width="100%" cellpadding="0" cellspacing="0">{bills_html}</table>

  <!-- FOOTER -->
  <tr><td style="padding:24px 0 0;border-top:1px solid #ffffff14;margin-top:20px">
    <div style="font-size:11px;color:#3a4060;text-align:center">
      Polymarket OSINT Monitor · Runs daily at 7 AM EDT · Analyst review required before escalation
    </div>
  </td></tr>

</table></td></tr></table>
</body></html>"""

    return html
