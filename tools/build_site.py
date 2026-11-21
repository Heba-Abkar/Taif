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
# upload confirmation: thumbnail + name + tick, shown as soon as a photo is chosen
tpl = sub1(
    '<div sc-camel-on-click="{{ startAnalysis }}"',
    '<div style="display:{{ uploadedDisplay }}; align-self:center; align-items:center; gap:14px; padding:10px 18px 10px 10px; border-radius:20px; background:rgba(255,255,255,0.28); border:1.5px solid #FFFFFF; animation:fadeUp 0.4s ease-out both;">'
    '<img src="{{ photoPreview }}" alt="" style="width:92px; height:68px; object-fit:cover; border-radius:12px; border:1px solid rgba(255,255,255,0.7);">'
    '<div style="display:flex; flex-direction:column; gap:2px;"><span style="font-size:15px; font-weight:800;">✓ تم رفع الصورة</span>'
    '<span style="font-size:12.5px; font-weight:600; color:rgba(255,255,255,0.85); max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; direction:ltr; text-align:right;">{{ photoName }}</span></div></div>'
    '<div sc-camel-on-click="{{ startAnalysis }}"',
    tpl,
)

# stages list -> live progress
tpl = rsub1(
    r'<div style="display:flex; flex-direction:column; gap:13px; font-size:15px; font-weight:600;">.*?(?=\n\s*<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">)',
    '<div style="display:flex; flex-direction:column; gap:13px; font-size:15px; font-weight:600;">'
    '<sc-for list="{{ stages }}" as="s" hint-placeholder-count="6">'
    '<div style="display:flex; align-items:center; gap:12px; color:{{ s.color }};">'
    '<span style="width:24px; height:24px; border-radius:50%; background:{{ s.bg }}; border:{{ s.bd }}; font-size:12px; display:grid; place-items:center; animation:{{ s.anim }};">{{ s.icon }}</span>'
    '<span>{{ s.label }}</span></div></sc-for></div>',
    tpl,
)
# detected-element chips
tpl = rsub1(
    r'<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">.*?</div>',
    '<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:6px;">'
    '<sc-for list="{{ detChips }}" as="d" hint-placeholder-count="5">'
    '<span style="font-size:12.5px; font-weight:600; padding:7px 14px; border-radius:999px; background:{{ d.bg }}; border:1px solid {{ d.bd }}; color:{{ d.color }};">{{ d.text }}</span>'
    '</sc-for></div>',
    tpl,
)
tpl = sub1(">نقرأ الواجهة…</div>", ">{{ readLabel }}</div>", tpl)

# score step: five real scores + strengths
for i, label in enumerate(["التكوين المعماري", "الألوان", "المواد والخامات", "الفتحات", "التظليل"]):
    tpl = rsub1(
        r'(<span>%s</span><span style="direction:ltr;">)\d+(</span></div><div style="[^"]*"><div style=")width:\d+%%' % re.escape(label),
        '\\1{{ s%d }}\\2width:{{ w%d }}%%' % (i, i),
        tpl,
    ) if False else re.sub(
        r'(<span>%s</span><span style="direction:ltr;">)\d+(</span></div><div style="[^"]*"><div style=")width:\d+%%' % re.escape(label),
        lambda mm, i=i: mm.group(1) + "{{ s%d }}" % i + mm.group(2) + "width:{{ w%d }}%%" % i,
        tpl,
        count=1,
    )
assert tpl.count("{{ w0 }}") == 1 and tpl.count("{{ w4 }}") == 1, "score rows not patched"
tpl = sub1("نقاط القوة: تناسق الكتل · وضوح المدخل", "{{ strengthsText }}", tpl)

# recommendations: real, building-specific text; generate button runs the generator
for i, old in enumerate([
    "نسب رأسية وإطارات غائرة تقترب من الطراز المرجعي.",
    "حجر البازلت والجرانيت والخشب المحلي.",
    "حضور أوضح مع مراعاة التناظر المركزي.",
    "معالجة تزيد العمق البصري في ضوء الجبال.",
    "موازنة بنسب تنسجم مع سياق عمارة الطائف.",
]):
    tpl = sub1(">%s</span>" % old, ">{{ rec%d }}</span>" % i, tpl)
a = tpl.index("<!-- Step 3: Recommendations -->")
b = tpl.index("<!-- Step 4: Before/After -->")
seg = tpl[a:b]
assert seg.count('sc-camel-on-click="{{ next }}"') == 1
tpl = tpl[:a] + seg.replace('sc-camel-on-click="{{ next }}"', 'sc-camel-on-click="{{ generateNow }}"') + tpl[b:]

# before / after: status label + real change chips
tpl = sub1(
    '<span style="position:absolute; bottom:18px; left:18px; font-size:12.5px;',
    '<span sc-camel-on-click="{{ retryAfter }}" style="display:{{ afterLabelDisplay }}; cursor:pointer; position:absolute; bottom:18px; left:18px; font-size:12.5px;',
    tpl,
)
tpl = sub1(">اسحب صورة التصور المقترح هنا</span>", ">{{ afterLabel }}</span>", tpl)
tpl = rsub1(
    r'(ماذا تغيّر؟</span>)((?:\s*<span style="font-size:13px; font-weight:600; padding:7px 16px;[^>]*>[^<]*</span>){5})',
    '\\1<sc-for list="{{ changeChips }}" as="c" hint-placeholder-count="5"><span style="font-size:13px; font-weight:600; padding:7px 16px; border-radius:999px; background:rgba(255,255,255,0.2); border:1px solid rgba(255,255,255,0.55);">{{ c.text }}</span></sc-for>'.replace("\\1", ""),
    tpl,
) if False else re.sub(
    r'(ماذا تغيّر؟</span>)((?:\s*<span style="font-size:13px; font-weight:600; padding:7px 16px;[^>]*>[^<]*</span>){5})',
    lambda mm: mm.group(1)
    + '<sc-for list="{{ changeChips }}" as="c" hint-placeholder-count="5"><span style="font-size:13px; font-weight:600; padding:7px 16px; border-radius:999px; background:rgba(255,255,255,0.2); border:1px solid rgba(255,255,255,0.55);">{{ c.text }}</span></sc-for>',
    tpl,
    count=1,
)
assert "{{ changeChips }}" in tpl

# chat: drop the fake highlight box, honest caption
tpl = rsub1(r'<div style="position:absolute; top:22%; right:28%;[^>]*></div>', "", tpl)
tpl = sub1("تمييز مباشر: النوافذ العلوية", "التصور المقترح من مِرْوَة", tpl)

# gallery: each tile opens a file picker (own photos), photo required to continue
tpl = sub1(
    "pick: e => { e.stopPropagation(); this.setState({ gallerySel: i, source: 'gallery' }); },",
    "pick: e => { e.stopPropagation(); this.setState({ gallerySel: i, source: 'gallery' }); this.pickPhoto('gallery-' + i); },",
    tpl,
)
tpl = sub1(
    "ready() { return this.state.source === 'gallery' ? this.state.gallerySel >= 0 : this.state.source === 'upload' ? this.state.phoneReceived : false; }",
    "ready() { return !!this.state.hasPhoto; }",
    tpl,
)
tpl = sub1(
    "simulatePhone: e => { e.stopPropagation(); this.setState({ phoneReceived: true }); },",
    "simulatePhone: e => { e.stopPropagation(); this.pickPhoto(); },",
    tpl,
)
tpl = sub1(">وصلت الصورة ← تابع</div>", ">اختر صورة من جهازك</div>", tpl)
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
    "    messages: [\n      { who: 'ai', text: 'أهلًا، أنا مِرْوَة. ارفع صورة واجهة منزلك وأكمل التحليل، وبعدها أشرح لك لماذا صُمّم التصور بهذه الطريقة.' }\n    ],\n    hasPhoto: false, photoPreview: '', photoName: '', analysis: null, analysisState: 'idle', stageDone: 0, afterState: 'idle', errMsg: ''",
    tpl,
)

tpl = sub1(
    """  ask(q, a) {
    this.setState(s => ({ messages: [...s.messages, { who: 'me', text: q }], typing: true }));
    clearTimeout(this._to);
    this._to = setTimeout(() => this.setState(s => ({ messages: [...s.messages, { who: 'ai', text: a }], typing: false })), 1100);
  }""",
    r"""  async ask(q, a) {
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
    } catch (e) { reply = 'تعذّر الاتصال بالمساعد، تأكد أن الباكند يعمل.'; }
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
  }
  setSlots(ids, url) {
    ids.forEach(id => { const el = document.getElementById(id); if (el) { el.setAttribute('src', url); el.src = url; } });
  }
  async shrink(file) {
    const bmp = await createImageBitmap(file);
    const k = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    const c = document.createElement('canvas');
    c.width = Math.round(bmp.width * k); c.height = Math.round(bmp.height * k);
    c.getContext('2d').drawImage(bmp, 0, 0, c.width, c.height);
    return await new Promise(r => c.toBlob(r, 'image/jpeg', 0.9));
  }
  pickPhoto(slotId) {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'image/*';
    inp.onchange = async () => {
      const f = inp.files && inp.files[0];
      if (!f) return;
      let blob = f;
      try { blob = await this.shrink(f); } catch (e) {}
      this._file = blob; this._analyzed = null; this._afterUrl = null; this._ctx = '';
      const rd = new FileReader();
      rd.onload = () => {
        this._photoUrl = rd.result; this.setState({ photoPreview: rd.result });
        this.setSlots(['analysis-facade', 'before-img'].concat(slotId ? [slotId] : []), rd.result);
      };
      rd.readAsDataURL(blob);
      this.setState({
        hasPhoto: true, phoneReceived: true, photoName: f.name || 'photo.jpg', analysis: null, analysisState: 'idle', stageDone: 0, afterState: 'idle', errMsg: '', score: 0,
        messages: [{ who: 'ai', text: 'وصلت الصورة. تابع لنبدأ التحليل.' }]
      });
    };
    inp.click();
  }
  async runAnalysis() {
    const file = this._file;
    this._analyzed = file;
    clearInterval(this._st);
    this.setState({ analysisState: 'running', stageDone: 0, errMsg: '' });
    this._st = setInterval(() => this.setState(s => ({ stageDone: Math.min(5, s.stageDone + 1) })), 1800);
    try {
      const fd = new FormData();
      fd.append('image', file, 'photo.jpg');
      const r = await fetch('/api/analyze-image', { method: 'POST', body: fd });
      const a = await r.json();
      if (!r.ok || typeof a.matchScore !== 'number') throw new Error(a.error || 'فشل التحليل');
      this._analysis = a;
      this._ctx = 'Building analysis (JSON, Arabic) — use it to explain WHY: ' + JSON.stringify(a);
      clearInterval(this._st);
      const tips = (a.strengths || []).slice(0, 3).map(t => '• ' + t).join('\n');
      this.setState({
        analysis: a, analysisState: 'done', stageDone: 6,
        messages: [{ who: 'ai', text: (a.summary || '') + (tips ? '\n' + tips : '') + '\nاسألني عن أي قرار في التصميم وأشرح لك لماذا.' }]
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
      fd.append('image', this._file, 'photo.jpg');
      fd.append('analysis', JSON.stringify(this._analysis));
      const r = await fetch('/api/generate-image', { method: 'POST', body: fd });
      const g = await r.json();
      if (!r.ok) throw new Error(g.error || 'فشل توليد التصور');
      const url = g.b64 ? 'data:' + (g.mime || 'image/png') + ';base64,' + g.b64 : g.url;
      if (!url) throw new Error('لم تصل صورة');
      this._afterUrl = url;
      this.setSlots(['after-img', 'chat-facade'], url);
      this.setState({ afterState: 'done' });
    } catch (e) {
      this.setState({ afterState: 'error', errMsg: String(e.message || e) });
    }
  }
  esc(t) { return String(t == null ? '' : t).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
  printReport() {
    const A = this._analysis;
    if (!A) { alert('أكمل التحليل أولاً ثم اطبع التقرير.'); return; }
    const e = t => this.esc(t);
    const names = [['composition', 'التكوين المعماري'], ['colors', 'الألوان'], ['materials', 'المواد والخامات'], ['openings', 'الفتحات'], ['shading', 'التظليل']];
    const recs = [['openings', 'معالجة الفتحات'], ['materials', 'المواد والخامات'], ['entrance', 'المدخل'], ['shading', 'التظليل'], ['palette', 'لوحة الألوان']];
    const qa = this.state.messages.slice(1).map(m => '<div class="msg ' + (m.who === 'me' ? 'me' : 'ai') + '"><b>' + (m.who === 'me' ? 'سؤالك' : 'مِرْوَة') + '</b><p>' + e(m.text).replace(/\n/g, '<br>') + '</p></div>').join('');
    const doc = '<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><title>تقرير مرآة عمارة الطائف</title><style>'
      + '@page{size:A4;margin:14mm}body{font-family:Tahoma,Arial,sans-serif;color:#2b1a24;line-height:1.8;font-size:13px}'
      + 'h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;border-bottom:2px solid #BE4A73;padding-bottom:4px;margin:22px 0 10px;color:#7E2B52}'
      + '.sub{color:#777;font-size:12px}.imgs{display:flex;gap:12px}.imgs figure{flex:1;margin:0}.imgs img{width:100%;border-radius:10px;border:1px solid #ddd}'
      + 'figcaption{text-align:center;font-weight:700;margin-top:4px}.score{font-size:42px;font-weight:800;color:#BE4A73}'
      + '.bar{height:8px;background:#eee;border-radius:9px;margin:2px 0 8px}.bar i{display:block;height:100%;background:#BE4A73;border-radius:9px}'
      + '.row{display:flex;justify-content:space-between}.card{border:1px solid #e5d3dc;border-radius:10px;padding:8px 12px;margin-bottom:8px;break-inside:avoid}'
      + '.card b{color:#7E2B52}.msg{padding:6px 10px;border-radius:10px;margin-bottom:6px;break-inside:avoid}.me{background:#f7e6ee}.ai{background:#f3f3f3}.msg p{margin:2px 0}'
      + '</style></head><body>'
      + '<h1>تقرير مرآة عمارة الطائف</h1><div class="sub">' + new Date().toLocaleDateString('ar-SA') + '</div>'
      + '<h2>قبل وبعد</h2><div class="imgs"><figure><img src="' + (this._photoUrl || '') + '"><figcaption>قبل · الواجهة الأصلية</figcaption></figure>'
      + (this._afterUrl ? '<figure><img src="' + this._afterUrl + '"><figcaption>بعد · التصور المقترح</figcaption></figure>' : '') + '</div>'
      + '<h2>التحليل</h2><p>' + e(A.summary) + '</p>'
      + '<h2>التقييم</h2><div class="score">' + A.matchScore + '<span style="font-size:16px"> / 100</span></div>'
      + names.map(n => '<div class="row"><span>' + n[1] + '</span><span>' + (A.scores[n[0]] || 0) + '</span></div><div class="bar"><i style="width:' + (A.scores[n[0]] || 0) + '%"></i></div>').join('')
      + ((A.strengths || []).length ? '<p><b>نقاط القوة:</b> ' + (A.strengths || []).map(e).join(' · ') + '</p>' : '')
      + '<h2>التوصيات</h2>'
      + recs.map(r => '<div class="card"><b>' + r[1] + '</b><br>' + e((A.recommendations || {})[r[0]]) + ((A.rationale || {})[r[0]] ? '<br><span class="sub">لماذا؟ ' + e(A.rationale[r[0]]) + '</span>' : '') + '</div>').join('')
      + ((A.changes || []).length ? '<p><b>ما الذي تغيّر في التصور:</b> ' + A.changes.map(e).join(' · ') + '</p>' : '')
      + (qa ? '<h2>أسئلتك ومحادثتك مع مِرْوَة</h2>' + qa : '')
      + '<p class="sub" style="margin-top:20px">تقرير استرشادي مبني على صورة واحدة، وليس بديلاً عن مراجعة جهة التصميم المعتمدة.</p>'
      + '</body></html>';
    const f = document.createElement('iframe');
    f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
    document.body.appendChild(f);
    f.onload = () => { try { f.contentWindow.focus(); f.contentWindow.print(); } catch (x) {} setTimeout(() => f.remove(), 60000); };
    f.srcdoc = doc;
  }""",
    tpl,
)

tpl = sub1("  renderVals() {\n", """  renderVals() {
    this.hooks();
    const S = this.state, A = S.analysis || {}, SC = A.scores || {}, RC = A.recommendations || {};
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
    const readLabel = S.analysisState === 'error' ? ('تعذّر التحليل: ' + S.errMsg) : S.analysisState === 'done' ? 'اكتمل التحليل ✓' : S.analysisState === 'running' ? 'نقرأ الواجهة…' : 'ارفع صورة لنبدأ';
    const afterLabel = S.afterState === 'loading' ? 'جارٍ توليد التصور من صورتك… قد يستغرق دقيقة' : S.afterState === 'error' ? ('تعذّر التوليد: ' + S.errMsg + ' — اضغط للإعادة') : S.afterState === 'idle' ? 'يُولَّد التصور بعد اكتمال التحليل' : '';
    const dflt = 'أكمل التحليل لتظهر توصية خاصة بواجهتك.';
    Object.assign(this, { _v: 1 });
""", tpl)

tpl = sub1("    return {\n      showAnnotations:", """    return {
      stages, detChips, readLabel, afterLabel,
      uploadedDisplay: S.hasPhoto ? 'flex' : 'none', photoPreview: S.photoPreview || '', photoName: S.photoName || '',
      afterLabelDisplay: afterLabel ? 'block' : 'none',
      retryAfter: () => { if (S.afterState === 'error' || S.afterState === 'idle') this.generateAfter(); },
      generateNow: () => { this.go(3); if (this.state.afterState === 'error' || this.state.afterState === 'idle') this.generateAfter(); },
      s0: sv('composition'), s1: sv('colors'), s2: sv('materials'), s3: sv('openings'), s4: sv('shading'),
      w0: sv('composition'), w1: sv('colors'), w2: sv('materials'), w3: sv('openings'), w4: sv('shading'),
      strengthsText: (A.strengths && A.strengths.length) ? 'نقاط القوة: ' + A.strengths.join(' · ') : 'نقاط القوة تظهر بعد التحليل',
      rec0: RC.openings || dflt, rec1: RC.materials || dflt, rec2: RC.entrance || dflt, rec3: RC.shading || dflt, rec4: RC.palette || dflt,
      changeChips: ((A.changes && A.changes.length) ? A.changes : ['المدخل', 'النوافذ', 'المواد', 'التظليل', 'الألوان']).map(text => ({ text })),
      sendChat: () => this.sendChat(),
      showAnnotations:""", tpl)
tpl = sub1('sc-camel-on-click="{{ askDefault }}"', 'sc-camel-on-click="{{ sendChat }}"', tpl)
tpl = sub1(
    '<span style="flex:1; font-size:14px; color:rgba(255,255,255,0.7); font-weight:600;">اكتب سؤالك عن التصميم…</span>',
    '<input id="taif-chat-input" type="text" placeholder="اكتب سؤالك عن التصميم…" '
    'style="flex:1; background:transparent; border:none; outline:none; color:#FFFFFF; font-size:14px; font-weight:600; font-family:inherit;">',
    tpl,
)

# re-serialise exactly like the bundler does
out = json.dumps(tpl, ensure_ascii=False).replace("</", "<\\u002F")
html = html[: m.start(2)] + out + html[m.end(2):]
open(dst, "w", encoding="utf8").write(html)
print("ok", len(html))
