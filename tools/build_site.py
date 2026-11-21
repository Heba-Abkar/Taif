#!/usr/bin/env python3
"""Patch the bundled demo site so every step talks to the real backend.

Usage: python3 -I tools/build_site.py <original.html> public/index.html
The original bundle stores its page template as a JSON string inside
<script type="__bundler/template">. We decode it, patch markup + Component logic,
and write it back in the same format. Serve the result from the backend (same origin).
"""
import json, re, sys

src, dst = sys.argv[1], sys.argv[2]
html = open(src, encoding="utf8").read()
m = re.search(r'(<script type="__bundler/template">\s*)(".*?")(\s*</script>)', html, re.S)
assert m, "template block not found"
tpl = json.loads(m.group(2))


def sub1(old, new, text):
    assert text.count(old) == 1, f"expected exactly one match for: {old[:70]!r} (got {text.count(old)})"
    return text.replace(old, new)


def rsub1(pattern, repl, text, flags=re.S):
    out, n = re.subn(pattern, lambda _m: repl, text, flags=flags)
    assert n == 1, f"expected exactly one regex match for: {pattern[:70]!r} (got {n})"
    return out


# ------------------------------------------------------------------ markup
# 1) upload card: the chosen photo shows INSIDE the square, no text line below
tpl = rsub1(
    r'<div style="display:\{\{ qrDisplay \}\};.*?\n              </div>(?=\n            </div>\n            <!-- gallery card -->)',
    '<div style="display:{{ qrDisplay }}; width:100%;">'
    '<div sc-camel-on-click="{{ simulatePhone }}" style-hover="background:rgba(255,255,255,0.3);" '
    'style="position:relative; width:100%; height:280px; border-radius:20px; overflow:hidden; cursor:pointer; background:rgba(74,36,54,0.35); border:2px dashed rgba(255,255,255,0.7); display:grid; place-items:center; transition:all 0.2s;">'
    '<img src="{{ photoPreview }}" alt="" style="display:{{ previewDisplay }}; position:absolute; inset:0; width:100%; height:100%; object-fit:contain;">'
    '<div style="display:{{ hintDisplay }}; flex-direction:column; align-items:center; gap:8px; text-align:center; padding:16px;">'
    '<span style="font-size:34px; line-height:1;">＋</span><span style="font-size:15px; font-weight:800;">اضغط لاختيار صورة الواجهة</span>'
    '<span style="font-size:12.5px; font-weight:600; color:rgba(255,255,255,0.85);">صورة واضحة للواجهة الأمامية</span></div>'
    '<span style="display:{{ previewDisplay }}; position:absolute; bottom:10px; right:10px; font-size:12.5px; font-weight:700; padding:6px 14px; border-radius:999px; background:rgba(74,36,54,0.65); border:1px solid rgba(255,255,255,0.7);">✓ صورتك · اضغط للتغيير</span>'
    '</div></div>',
    tpl,
)
tpl = rsub1(
    r'امسح الباركود بجوالك وصوّر الواجهة',
    'اختر صورة الواجهة من جهازك',
    tpl,
)

# 2) gallery tiles show the real sample photo
tpl = sub1(
    '<image-slot id="{{ g.slotId }}" shape="rect" placeholder="{{ g.label }}"></image-slot>',
    '<img src="{{ g.src }}" alt="" style="display:{{ g.imgDisplay }}; position:absolute; inset:0; width:100%; height:100%; object-fit:cover;">',
    tpl,
)

# 3) stages list -> live progress, detected chips, clear "done" state
tpl = rsub1(
    r'<div style="display:flex; flex-direction:column; gap:13px; font-size:15px; font-weight:600;">.*?(?=\n\s*<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">)',
    '<div style="display:flex; flex-direction:column; gap:13px; font-size:15px; font-weight:600;">'
    '<sc-for list="{{ stages }}" as="s" hint-placeholder-count="6">'
    '<div style="display:flex; align-items:center; gap:12px; color:{{ s.color }};">'
    '<span style="width:24px; height:24px; border-radius:50%; background:{{ s.bg }}; border:{{ s.bd }}; font-size:12px; display:grid; place-items:center; animation:{{ s.anim }};">{{ s.icon }}</span>'
    '<span>{{ s.label }}</span></div></sc-for></div>',
    tpl,
)
tpl = rsub1(
    r'<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">.*?</div>',
    '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">'
    '<sc-for list="{{ detChips }}" as="d" hint-placeholder-count="5">'
    '<span style="font-size:12.5px; font-weight:600; padding:7px 14px; border-radius:999px; background:{{ d.bg }}; border:1px solid {{ d.bd }}; color:{{ d.color }};">{{ d.text }}</span>'
    '</sc-for></div>'
    '<div style="display:{{ doneDisplay }}; flex-direction:column; gap:12px; margin-top:10px; padding:18px 20px; border-radius:20px; background:linear-gradient(160deg,rgba(255,183,212,0.34),rgba(255,255,255,0.22)); border:1.5px solid #FFFFFF; animation:fadeUp 0.5s ease-out both;">'
    '<span style="font-size:20px; font-weight:800;">✓ اكتمل التحليل</span>'
    '<span style="font-size:14.5px; font-weight:600; line-height:1.9;">{{ verdict }}</span>'
    '<div sc-camel-on-click="{{ next }}" style-hover="transform:translateY(-2px);" '
    'style="align-self:flex-start; background:linear-gradient(160deg,#E4759D,#BE4A73); font-size:15px; font-weight:800; padding:11px 28px; border-radius:999px; box-shadow:0 12px 28px rgba(107,53,80,0.45), inset 0 1px 0 rgba(255,255,255,0.6); cursor:pointer;">شاهد التقييم ←</div>'
    '</div>',
    tpl,
)
tpl = sub1(
    "padding:10px 20px; border-radius:999px; background:rgba(74,36,54,0.5);",
    "padding:10px 20px; border-radius:999px; background:{{ readBg }};",
    tpl,
)
tpl = sub1(">نقرأ الواجهة…</div>", ">{{ readLabel }}</div>", tpl)

# 4) score step: five real scores, each with a short evidence note
for i, label in enumerate(["التكوين المعماري", "الألوان", "المواد والخامات", "الفتحات", "التظليل"]):
    new_tpl, n = re.subn(
        r'<span>%s</span><span style="direction:ltr;">\d+</span>(</div><div style="[^"]*"><div style=")width:\d+%%' % re.escape(label),
        lambda mm, i=i, label=label: '<span>%s<br><span style="font-size:12px; font-weight:500; color:rgba(255,255,255,0.78);">{{ n%d }}</span></span><span style="direction:ltr;">{{ s%d }}</span>' % (label, i, i)
        + mm.group(1) + "width:{{ w%d }}%%" % i,
        tpl,
        count=1,
    )
    assert n == 1, f"score row {label} not patched"
    tpl = new_tpl
tpl = sub1("نقاط القوة: تناسق الكتل · وضوح المدخل", "{{ strengthsText }}", tpl)

# 5) recommendations: where + what, and the real reason
for i, old in enumerate([
    "نسب رأسية وإطارات غائرة تقترب من الطراز المرجعي.",
    "حجر البازلت والجرانيت والخشب المحلي.",
    "حضور أوضح مع مراعاة التناظر المركزي.",
    "معالجة تزيد العمق البصري في ضوء الجبال.",
    "موازنة بنسب تنسجم مع سياق عمارة الطائف.",
]):
    tpl = sub1(
        ">%s</span>" % old,
        '>{{ rec%d }}</span><span style="font-size:13px; line-height:1.8; color:rgba(255,255,255,0.78);">{{ why%d }}</span>' % (i, i),
        tpl,
    )
# the last card of step 3 is just the next step (before / after), not a second "generate"
a = tpl.index("<!-- Step 3: Recommendations -->")
b = tpl.index("<!-- Step 4: Before/After -->")
seg = tpl[a:b]
assert seg.count('sc-camel-on-click="{{ next }}"') == 1
for old, new in ((">أنشئ</span>", ">شاهد</span>"), (">التصور</span>", ">قبل</span>"), (">الآن</span>", ">وبعد</span>")):
    seg = sub1(old, new, seg)
tpl = tpl[:a] + seg + tpl[b:]

# 6) before / after: status label + real change chips
tpl = sub1(
    '<span style="position:absolute; bottom:18px; left:18px; font-size:12.5px;',
    '<span sc-camel-on-click="{{ retryAfter }}" style="display:{{ afterLabelDisplay }}; cursor:pointer; position:absolute; bottom:18px; left:18px; font-size:12.5px;',
    tpl,
)
tpl = sub1(">اسحب صورة التصور المقترح هنا</span>", ">{{ afterLabel }}</span>", tpl)
tpl = rsub1(
    r'(ماذا تغيّر؟</span>)((?:\s*<span style="font-size:13px; font-weight:600; padding:7px 16px;[^>]*>[^<]*</span>){5})',
    '\\1<sc-for list="{{ changeChips }}" as="c" hint-placeholder-count="5"><span style="font-size:13px; font-weight:600; padding:7px 16px; border-radius:999px; background:rgba(255,255,255,0.2); border:1px solid rgba(255,255,255,0.55);">{{ c.text }}</span></sc-for>'.replace("\\1", "ماذا تغيّر؟</span>"),
    tpl,
)

# 7) chat: drop the fake highlight box, honest caption, real input
tpl = rsub1(r'<div style="position:absolute; top:22%; right:28%;[^>]*></div>', "", tpl)
tpl = sub1("تمييز مباشر: النوافذ العلوية", "التصور المقترح من مِرْوَة", tpl)
tpl = sub1('sc-camel-on-click="{{ askDefault }}"', 'sc-camel-on-click="{{ sendChat }}"', tpl)
tpl = sub1(
    '<span style="flex:1; font-size:14px; color:rgba(255,255,255,0.7); font-weight:600;">اكتب سؤالك عن التصميم…</span>',
    '<input id="taif-chat-input" type="text" placeholder="اكتب سؤالك عن التصميم…" '
    'style="flex:1; background:transparent; border:none; outline:none; color:#FFFFFF; font-size:14px; font-weight:600; font-family:inherit;">',
    tpl,
)

# 8) wiring in renderVals / component
tpl = sub1(
    "pick: e => { e.stopPropagation(); this.setState({ gallerySel: i, source: 'gallery' }); },",
    "pick: e => { e.stopPropagation(); },",
    tpl,
)
tpl = rsub1(
    r"galleryItems: \['فيلا حديثة', 'منزل بسيط', 'مبنى تجاري'\]\.map\(\(label, i\) => \(\{.*?\}\)\),",
    """galleryItems: (S.gallery.length ? S.gallery : [{ label: 'نماذج قريباً' }, { label: 'نماذج قريباً' }, { label: 'نماذج قريباً' }]).map((g, i) => ({
        label: g.label, src: g.url || '', imgDisplay: g.url ? 'block' : 'none',
        pick: e => { e.stopPropagation(); if (g.url) this.pickGallery(g, i); },
        bd: S.gallerySel === i ? '#FFFFFF' : 'rgba(255,255,255,0.35)',
        checkDisplay: S.gallerySel === i ? 'grid' : 'none'
      })),""",
    tpl,
)
tpl = sub1(
    "chips: chipData.map(c => ({ label: c.q, ask: () => this.ask(c.q, c.a) })),",
    """chips: ((A.recommendations || []).filter(r => r.where).length
        ? (A.recommendations || []).filter(r => r.where).slice(0, 3).map(r => 'لماذا غيّرتم ' + r.element + '؟').concat(['كيف أرفع التقييم؟'])
        : chipData.map(c => c.q)).map(q => ({ label: q, ask: () => this.ask(q) })),""",
    tpl,
)
tpl = sub1(
    "simulatePhone: e => { e.stopPropagation(); this.setState({ phoneReceived: true }); },",
    "simulatePhone: e => { e.stopPropagation(); this.pickPhoto(); },",
    tpl,
)
tpl = sub1(
    "ready() { return this.state.source === 'gallery' ? this.state.gallerySel >= 0 : this.state.source === 'upload' ? this.state.phoneReceived : false; }",
    "ready() { return !!this.state.hasPhoto; }",
    tpl,
)
tpl = sub1("printReport: () => { window.print(); },", "printReport: () => this.printReport(),", tpl)

# ------------------------------------------------------------------ logic
tpl = sub1(
    "go(i) { this.setState({ step: i }); if (i === 1) this.animateScore(); }",
    """go(i) {
    this.setState({ step: i });
    if (i === 0 && this.state.hasPhoto && this._analyzed !== this._file) this._ap = this.runAnalysis();
    if (i === 1) (this._ap || Promise.resolve()).then(() => this.animateScore());
  }""",
    tpl,
)
tpl = sub1(
    "this.setState({ score: Math.round(82 * (1 - Math.pow(1 - p, 3))) });",
    "this.setState({ score: Math.round(((this.state.analysis && this.state.analysis.matchScore) || 0) * (1 - Math.pow(1 - p, 3))) });",
    tpl,
)
tpl = sub1(
    "    messages: [\n      { who: 'ai', text: 'أهلًا! انتهينا من تصور واجهتك. اسألني عن أي تغيير — لماذا اقترحناه وما فائدته.' }\n    ]",
    "    messages: [\n      { who: 'ai', text: 'أهلًا، أنا مِرْوَة. ارفع صورة واجهة منزلك وأكمل التحليل، وبعدها أشرح لك لماذا صُمّم التصور بهذه الطريقة.' }\n    ],\n    hasPhoto: false, photoPreview: '', afterSrc: '', gallery: [], gallerySel: -1, analysis: null, analysisState: 'idle', stageDone: 0, afterState: 'idle', errMsg: ''",
    tpl,
)

tpl = sub1(
    """  ask(q, a) {
    this.setState(s => ({ messages: [...s.messages, { who: 'me', text: q }], typing: true }));
    clearTimeout(this._to);
    this._to = setTimeout(() => this.setState(s => ({ messages: [...s.messages, { who: 'ai', text: a }], typing: false })), 1100);
  }""",
    r"""  async ask(q) {
    const history = [...this.state.messages, { who: 'me', text: q }];
    this.setState({ messages: history, typing: true });
    let reply = null;
    try {
      const r = await fetch('/api/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          context: this._ctx || '',
          messages: history.slice(-14).map(m => ({ role: m.who === 'me' ? 'user' : 'assistant', content: m.text }))
        })
      });
      const j = await r.json();
      reply = j.reply || ('تعذّر الحصول على الإجابة: ' + (j.error || 'خطأ غير معروف'));
    } catch (e) { reply = 'تعذّر الاتصال بالمساعد، حاول مرة أخرى.'; }
    this.setState(s => ({ messages: [...s.messages, { who: 'ai', text: reply }], typing: false }));
  }
  sendChat() {
    const el = document.getElementById('taif-chat-input');
    const q = el && el.value.trim();
    if (!q) return;
    el.value = '';
    this.ask(q);
  }
  hooks() {
    if (this._hooked) return;
    this._hooked = true;
    document.addEventListener('keydown', e => {
      if (e.key === 'Enter' && e.target && e.target.id === 'taif-chat-input') this.sendChat();
    });
    fetch('/api/gallery').then(r => r.json()).then(g => this.setState({ gallery: g })).catch(() => {});
  }
  async shrink(file) {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    const c = document.createElement('canvas');
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    return await new Promise(r => c.toBlob(r, 'image/jpeg', 0.9));
  }
  newPhoto(blob, previewUrl, extra) {
    this._file = blob; this._analyzed = null; this._analysis = null; this._afterUrl = null; this._ctx = ''; this._photoUrl = previewUrl;
    this.setState(Object.assign({
      hasPhoto: true, photoPreview: previewUrl, analysis: null, analysisState: 'idle', stageDone: 0, afterState: 'idle', afterSrc: '', errMsg: '', score: 0,
      messages: [{ who: 'ai', text: 'وصلت الصورة. تابع لنبدأ التحليل.' }]
    }, extra || {}));
  }
  pickPhoto() {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'image/*';
    inp.onchange = async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      let blob = f;
      try { blob = await this.shrink(f); } catch (e) {}
      const rd = new FileReader();
      rd.onload = () => this.newPhoto(blob, rd.result, { source: 'upload', gallerySel: -1 });
      rd.readAsDataURL(blob);
    };
    inp.click();
  }
  async pickGallery(g, i) {
    try {
      const blob = await (await fetch(g.url)).blob(); // original bytes: the server recognises a photo it already handled
      this.newPhoto(blob, g.url, { source: 'gallery', gallerySel: i });
    } catch (e) {}
  }
  async runAnalysis() {
    const file = this._file;
    this._analyzed = file;
    clearInterval(this._st);
    this.setState({ analysisState: 'running', stageDone: 0, errMsg: '' });
    this._st = setInterval(() => this.setState(s => ({ stageDone: Math.min(5, s.stageDone + 1) })), 1800);
    try {
      const fd = new FormData();
      fd.append('image', file, 'photo');
      const r = await fetch('/api/analyze-image', { method: 'POST', body: fd });
      const a = await r.json();
      if (!r.ok || typeof a.matchScore !== 'number') throw new Error(a.error || 'فشل التحليل');
      this._analysis = a;
      this._ctx = 'Building analysis (JSON, Arabic) — use it to explain WHY, with exact places: ' + JSON.stringify(a);
      clearInterval(this._st);
      this.setState({
        analysis: a, analysisState: 'done', stageDone: 6,
        messages: [{ who: 'ai', text: (a.summary || '') + '\\nاسألني عن أي قرار في التصميم وأشرح لك لماذا.' }]
      });
      this.generateAfter();
    } catch (e) {
      clearInterval(this._st);
      this._analyzed = null;
      this.setState({ analysisState: 'error', errMsg: String(e.message || e) });
    }
  }
  async generateAfter() {
    if (!this._file || !this._analysis) return;
    this.setState({ afterState: 'loading' });
    try {
      const fd = new FormData();
      fd.append('image', this._file, 'photo');
      fd.append('analysis', JSON.stringify(this._analysis));
      const r = await fetch('/api/generate-image', { method: 'POST', body: fd });
      const g = await r.json();
      if (!r.ok) throw new Error(g.error || 'فشل توليد التصور');
      const url = g.b64 ? 'data:' + (g.mime || 'image/png') + ';base64,' + g.b64 : g.url;
      if (!url) throw new Error('لم تصل صورة');
      this._afterUrl = url;
      this.setState({ afterSrc: url });
      this.setState({ afterState: 'done' });
    } catch (e) {
      this.setState({ afterState: 'error', errMsg: String(e.message || e) });
    }
  }
  esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  async toDataUrl(u) {
    const b = await (await fetch(u)).blob();
    return await new Promise(r => { const rd = new FileReader(); rd.onload = () => r(rd.result); rd.readAsDataURL(b); });
  }
  async printReport() {
    const A = this._analysis;
    if (!A) { alert('أكمل التحليل أولاً ثم اطبع التقرير.'); return; }
    const e = t => this.esc(t);
    const O = location.origin;
    const logo = await this.toDataUrl('/brand/mirat-icon.png').catch(() => '');
        const before = this._photoUrl ? await this.toDataUrl(this._photoUrl).catch(() => this._photoUrl) : '';
    const names = [['composition', 'التكوين المعماري'], ['colors', 'الألوان'], ['materials', 'المواد والخامات'], ['openings', 'الفتحات'], ['shading', 'التظليل']];
    const recs = (A.recommendations || []).filter(r => r.where);
    const qa = [];
    const ms = this.state.messages.slice(1);
    for (let i = 0; i < ms.length - 1; i++) if (ms[i].who === 'me' && ms[i + 1].who === 'ai') qa.push([ms[i].text, ms[i + 1].text]);
    const cut = (t, n) => { t = String(t || '').replace(/\\s+/g, ' ').trim(); return t.length > n ? t.slice(0, n - 1) + '…' : t; };
    const col = s => s >= 75 ? '#7E4BA8' : s >= 55 ? '#B26984' : '#E4759D';
    const doc = '<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><title>تقرير مرآة عمارة الطائف</title><style>'
      + '@font-face{font-family:Cairo;font-weight:400;src:url(' + O + '/fonts/cairo-400.woff2);unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200E}@font-face{font-family:Cairo;font-weight:600;src:url(' + O + '/fonts/cairo-600.woff2);unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200E}@font-face{font-family:Cairo;font-weight:700;src:url(' + O + '/fonts/cairo-700.woff2);unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200E}@font-face{font-family:Cairo;font-weight:800;src:url(' + O + '/fonts/cairo-800.woff2);unicode-range:U+0600-06FF,U+0750-077F,U+08A0-08FF,U+FB50-FDFF,U+FE70-FEFF,U+200C-200E}@font-face{font-family:Cairo;font-weight:400;src:url(' + O + '/fonts/cairo-latin-400.woff2);unicode-range:U+0000-05FF,U+2000-206F}@font-face{font-family:Cairo;font-weight:600 800;src:url(' + O + '/fonts/cairo-latin-700.woff2);unicode-range:U+0000-05FF,U+2000-206F}@page{size:A4;margin:9mm}*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}'
      + 'body{margin:0;font-family:Cairo,Tahoma,sans-serif;color:#2b1a24;font-size:12px;line-height:1.65}'
      + '#page{width:100%}.head{display:flex;align-items:center;justify-content:space-between;background:linear-gradient(160deg,#B26984,#6B3550);border-radius:12px;padding:9px 16px;color:#fff;gap:12px}'
      + '.head .m{height:38px;width:38px;border-radius:9px;background:#000}.head .c{height:34px}.head .t{flex:1;text-align:right;margin-right:4px}.head b{font-size:16px}.head span{font-size:11px;opacity:.85}'
      + '.imgs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}.imgs figure{margin:0;position:relative;height:200px;border-radius:10px;overflow:hidden;background:#f1e6ec}'
      + '.imgs img{width:100%;height:100%;object-fit:contain;display:block}.tag{position:absolute;top:7px;right:7px;background:rgba(90,42,68,.85);color:#fff;border-radius:99px;padding:2px 11px;font-size:11px;font-weight:700}'
      + '.tag.a{background:#BE4A73}.grid{display:grid;grid-template-columns:150px 1fr;gap:12px;align-items:center;border:1px solid #ecd3df;border-radius:12px;padding:8px 12px}'
      + '.ring{width:104px;height:104px;border-radius:50%;display:grid;place-items:center;margin:auto}.ring div{width:80px;height:80px;border-radius:50%;background:#fff;display:grid;place-items:center;text-align:center}'
      + '.ring b{font-size:27px;line-height:1;color:#6B3550}.ring small{font-size:9.5px;color:#777}.cap{text-align:center;font-size:10.5px;font-weight:700;margin-top:2px}'
      + '.row{display:grid;grid-template-columns:96px 1fr 26px;gap:7px;align-items:center;margin:2.5px 0}.row span{font-weight:700}.bar{height:7px;background:#eee;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;border-radius:9px}'
      + '.note{grid-column:1/4;font-size:10px;color:#777;margin-top:-2px}'
      + 'h2{font-size:12.5px;margin:9px 0 4px;color:#7E2B52;border-right:4px solid #BE4A73;padding-right:7px}'
      + '.sum{background:#faf1f5;border-radius:10px;padding:6px 11px}.sum b{display:block;margin-bottom:2px}'
      + '.rec{display:grid;grid-template-columns:96px 1fr;gap:7px;padding:3px 0;border-bottom:1px dashed #ecd3df}.rec:last-child{border:0}.rec b{color:#7E2B52}.rec i{display:block;font-style:normal;color:#777;font-size:10px}'
      + '.qa{font-size:10.5px;background:#f6f6f6;border-radius:8px;padding:4px 9px;margin-top:3px}.foot{margin-top:7px;font-size:9px;color:#888;text-align:center}'
      + '</style></head><body><div id="page">'
      + '<div class="head"><img class="m" src="' + logo + '"><div class="t"><b>تقرير مرآة عمارة الطائف</b><br><span>تحليل الواجهة · ' + new Date().toLocaleDateString('ar-SA') + '</span></div></div>'
      + '<div class="imgs"><figure><img src="' + before + '"><span class="tag">قبل</span></figure>'
      + (this._afterUrl ? '<figure><img src="' + this._afterUrl + '"><span class="tag a">بعد · التصور المقترح</span></figure>' : '<figure style="display:grid;place-items:center;color:#999">لم يُولَّد التصور بعد</figure>') + '</div>'
      + '<div class="grid"><div><div class="ring" style="background:conic-gradient(#E4759D 0deg,#7E4BA8 ' + Math.round(A.matchScore * 3.6) + 'deg,#eee 0)"><div><b>' + A.matchScore + '</b><small>من 100</small></div></div><div class="cap">التوافق مع طراز الطائف</div></div><div>'
      + names.map(n => { const v = A.scores[n[0]] || 0; return '<div class="row"><span>' + n[1] + '</span><div class="bar"><i style="width:' + v + '%;background:' + col(v) + '"></i></div><b>' + v + '</b><div class="note">' + e(cut((A.scoreNotes || {})[n[0]], 90)) + '</div></div>'; }).join('')
      + '</div></div>'
      + '<h2>الخلاصة</h2><div class="sum"><b>' + e(A.verdict) + '</b>' + e(cut(A.summary, 330)) + '</div>'
      + (recs.length ? '<h2>ماذا نعدّل ولماذا؟</h2>' + recs.map(r => '<div class="rec"><b>' + e(r.element) + '</b><div>' + e(cut(r.where + ': ' + r.change, 150)) + '<i>السبب: ' + e(cut(r.why, 130)) + '</i></div></div>').join('') : '')
      + (qa.length ? '<h2>سؤالك لمِرْوَة</h2>' + qa.slice(-1).map(p => '<div class="qa"><b>' + e(cut(p[0], 90)) + '</b><br>' + e(cut(p[1], 230)) + '</div>').join('') : '')
      + '<div class="foot">تقرير استرشادي مبني على صورة واحدة، وليس بديلاً عن مراجعة الجهة المعتمدة · مرآة عمارة الطائف</div>'
      + '</div><script>window.addEventListener("load",function(){var p=document.getElementById("page");var max=1020;var h=p.scrollHeight;if(h>max){var k=max/h;p.style.transform="scale("+k+")";p.style.transformOrigin="top center";p.style.width=(100/k)+"%";p.style.marginRight=((100/k-100)/-2)+"%"}});<\\/script></body></html>';
    const f = document.createElement('iframe');
    f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
    document.body.appendChild(f);
    f.onload = () => { const go = () => setTimeout(() => { try { f.contentWindow.focus(); f.contentWindow.print(); } catch (x) {} setTimeout(() => f.remove(), 60000); }, 300); try { f.contentWindow.document.fonts.ready.then(go); } catch (x) { go(); } };
    f.srcdoc = doc;
  }""",
    tpl,
)

tpl = sub1("  renderVals() {\n", """  renderVals() {
    this.hooks();
    const S = this.state, A = S.analysis || {};
    const RB = {}; (A.recommendations || []).forEach(r => { RB[r.id] = r; });
    const rt = id => (RB[id] && RB[id].where) ? RB[id].where + ': ' + RB[id].change : 'أكمل التحليل لتظهر توصية خاصة بواجهتك.';
    const rw = id => (RB[id] && RB[id].why) ? 'السبب: ' + RB[id].why : '';
    const SN = A.scoreNotes || {}, SC = A.scores || {};
    const stageLabels = ['اكتشاف عناصر الواجهة', 'تحليل المواد والألوان', 'قراءة الفتحات والكتل', 'فهم عناصر التظليل والمعالجة', 'مقارنة العناصر بالموجهات المرجعية', 'إعداد التقييم'];
    const stages = stageLabels.map((label, i) => {
      const done = S.stageDone > i, active = !done && S.stageDone === i && S.analysisState === 'running';
      return {
        label, icon: done ? '✓' : active ? '◐' : '○',
        color: done || active ? '#FFFFFF' : 'rgba(255,255,255,0.7)',
        bg: done ? 'rgba(255,255,255,0.35)' : 'transparent',
        bd: done ? '1px solid #FFFFFF' : active ? '1.5px solid #FFFFFF' : '1px solid rgba(255,255,255,0.5)',
        anim: active ? 'pulse 1.5s ease-in-out infinite' : 'none'
      };
    });
    const det = A.detected || {};
    const detChips = [['windows', 'النوافذ'], ['entrance', 'المدخل'], ['materials', 'المواد'], ['colors', 'الألوان'], ['shading', 'التظليل']].map(([k, t]) => {
      const on = !!det[k];
      return { text: (on ? '✓ ' : '') + t, bg: on ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.14)', bd: on ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.4)', color: on ? '#FFFFFF' : 'rgba(255,255,255,0.8)' };
    });
    const sv = k => (typeof SC[k] === 'number' ? SC[k] : 0);
    const readLabel = S.analysisState === 'error' ? ('تعذّر التحليل: ' + S.errMsg) : S.analysisState === 'done' ? '✓ اكتمل التحليل' : S.analysisState === 'running' ? 'نقرأ الواجهة…' : 'ارفع صورة لنبدأ';
    const readBg = S.analysisState === 'done' ? 'linear-gradient(160deg,#E4759D,#BE4A73)' : S.analysisState === 'error' ? 'rgba(192,80,77,0.85)' : 'rgba(74,36,54,0.5)';
    const afterLabel = S.afterState === 'loading' ? 'جارٍ توليد التصور من صورتك… قد يستغرق دقيقة' : S.afterState === 'error' ? ('تعذّر التوليد: ' + S.errMsg + ' — اضغط للإعادة') : S.afterState === 'idle' ? 'يُولَّد التصور بعد اكتمال التحليل' : '';
""", tpl)

tpl = sub1("    return {\n      showAnnotations:", """    return {
      stages, detChips, readLabel, readBg, afterLabel,
      afterSrc: S.afterSrc || '', afterImgDisplay: S.afterSrc ? 'block' : 'none',
      navStartDisplay: S.view === 'journey' ? 'none' : 'block',
      prevDisplay: S.step > -1 ? 'flex' : 'none',
      nextDisplay: (S.step === 1 || S.step === 4) ? 'flex' : 'none',
      nextLabel: S.step === 1 ? 'شاهد التوصيات' : 'اطبع التقرير',
      previewDisplay: S.photoPreview ? 'block' : 'none', hintDisplay: S.photoPreview ? 'none' : 'flex', photoPreview: S.photoPreview || '',
      doneDisplay: S.analysisState === 'done' ? 'flex' : 'none', verdict: A.verdict || '',
      afterLabelDisplay: afterLabel ? 'block' : 'none',
      retryAfter: () => { if (S.afterState === 'error' || S.afterState === 'idle') this.generateAfter(); },
      s0: sv('composition'), s1: sv('colors'), s2: sv('materials'), s3: sv('openings'), s4: sv('shading'),
      w0: sv('composition'), w1: sv('colors'), w2: sv('materials'), w3: sv('openings'), w4: sv('shading'),
      n0: SN.composition || '', n1: SN.colors || '', n2: SN.materials || '', n3: SN.openings || '', n4: SN.shading || '',
      strengthsText: (A.strengths && A.strengths.length) ? 'نقاط القوة: ' + A.strengths.join(' · ') : 'نقاط القوة تظهر بعد التحليل',
      rec0: rt('openings'), rec1: rt('materials'), rec2: rt('entrance'), rec3: rt('shading'), rec4: rt('palette'),
      why0: rw('openings'), why1: rw('materials'), why2: rw('entrance'), why3: rw('shading'), why4: rw('palette'),
      changeChips: ((A.changes && A.changes.length) ? A.changes : ['المدخل', 'النوافذ', 'المواد', 'التظليل', 'الألوان']).map(text => ({ text })),
      sendChat: () => this.sendChat(),
      showAnnotations:""", tpl)


# ---- review round: nav, step bar, images
tpl = rsub1(r'<div style-hover="transform:translateY\(-2px\);" style="width:42px; height:42px;.*?</span>\s*</div>\s*(?=<div sc-camel-on-click="\{\{ startJourney \}\}")', '', tpl)
tpl = sub1('style="background:linear-gradient(160deg,#E4759D,#BE4A73); color:#FFFFFF; font-size:15.5px; font-weight:700; padding:11px 28px;', 'style="display:{{ navStartDisplay }}; background:linear-gradient(160deg,#E4759D,#BE4A73); color:#FFFFFF; font-size:15.5px; font-weight:700; padding:11px 28px;', tpl)
tpl = sub1('style="display:flex; align-items:center; gap:8px; padding:11px 26px;', 'style="display:{{ prevDisplay }}; align-items:center; gap:8px; padding:11px 26px;', tpl)
tpl = sub1('style="display:flex; align-items:center; gap:8px; padding:11px 30px; border-radius:999px; background:linear-gradient(160deg,#E4759D,#BE4A73); font-size:14.5px;', 'style="display:{{ nextDisplay }}; align-items:center; gap:8px; padding:11px 30px; border-radius:999px; background:linear-gradient(160deg,#E4759D,#BE4A73); font-size:14.5px;', tpl)
tpl = sub1('الخطوة التالية ›</div>', '{{ nextLabel }} ›</div>', tpl)
tpl = sub1('<image-slot id="analysis-facade" shape="rect" placeholder="صورة الواجهة قيد التحليل"></image-slot>', '<img src="{{ photoPreview }}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:contain; background:rgba(74,36,54,0.35);">', tpl)
tpl = sub1('<image-slot id="before-img" shape="rect" placeholder="الواجهة الأصلية — BEFORE"></image-slot>', '<img src="{{ photoPreview }}" alt="" style="position:absolute; inset:0; width:100%; height:100%; object-fit:contain; background:rgba(74,36,54,0.35);">', tpl)
tpl = sub1('<image-slot id="after-img" shape="rect" placeholder=" "></image-slot>', '<img src="{{ afterSrc }}" alt="" style="display:{{ afterImgDisplay }}; position:absolute; inset:0; width:100%; height:100%; object-fit:contain;">', tpl)
tpl = sub1('<image-slot id="chat-facade" shape="rect" placeholder="التصور المقترح"></image-slot>', '<img src="{{ afterSrc }}" alt="" style="display:{{ afterImgDisplay }}; position:absolute; inset:0; width:100%; height:100%; object-fit:contain;">', tpl)

# re-serialise exactly like the bundler does
out = json.dumps(tpl, ensure_ascii=False).replace("</", "<\\u002F")
html = html[: m.start(2)] + out + html[m.end(2):]
html = html.replace("<head>", '<head><link rel="icon" href="/brand/mirat-icon.png">', 1)
open(dst, "w", encoding="utf8").write(html)
print("ok", len(html))
