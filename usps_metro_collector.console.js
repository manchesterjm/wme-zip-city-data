// USPS Cities-by-ZIP collector v3 — batch + pause to beat the ~10/window limit.
// Run in DevTools console on https://tools.usps.com/zip-code-lookup.htm?citybyzipcode
// Resumable (localStorage). Downloads usps_metro.json when finished.
// Takes ~15-20 min; leave the tab open and focused. Re-run if it ends < 106.
(async () => {
  const zips = [
    "80001","80002","80003","80004","80006","80007","80010","80011","80013","80015",
    "80017","80018","80019","80020","80024","80025","80026","80027","80030","80031",
    "80034","80035","80036","80037","80038","80040","80041","80042","80044","80045",
    "80046","80047","80102","80103","80104","80105","80107","80109","80110","80113",
    "80116","80117","80118","80120","80121","80122","80123","80125","80127","80128",
    "80129","80131","80137","80138","80150","80151","80155","80160","80161","80162",
    "80163","80201","80202","80203","80204","80205","80206","80207","80209","80210",
    "80211","80212","80214","80215","80216","80217","80218","80219","80220","80221",
    "80222","80223","80224","80226","80227","80228","80229","80230","80231","80232",
    "80234","80235","80236","80237","80238","80239","80248","80249","80250","80260",
    "80264","80265","80290","80293","80294","80299"
  ];
  const KEY = 'uspsMetroData';
  const BATCH = 8;       // requests before a cooldown
  const PAUSE = 75000;   // cooldown to let the rate window reset
  const out = JSON.parse(localStorage.getItem(KEY) || '{}');
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const todo = zips.filter(z => !out[z] || out[z].resultStatus !== 'SUCCESS');
  console.log('Need ' + todo.length + ' of ' + zips.length + '. ~' +
              Math.ceil(todo.length / BATCH) + ' batches x 75s. Leave tab open.');
  let sinceBreak = 0;
  for (let i = 0; i < todo.length; ) {
    const zip = todo[i];
    let blocked = false;
    try {
      const res = await fetch('https://tools.usps.com/tools/app/ziplookup/cityByZip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
        body: 'zip=' + zip,
        credentials: 'include'
      });
      if (res.redirected) { blocked = true; }
      else {
        const data = await res.json();
        if (data && data.resultStatus === 'SUCCESS') {
          out[zip] = data;
          localStorage.setItem(KEY, JSON.stringify(out));
          i++; sinceBreak++;
        } else { blocked = true; }
      }
    } catch (e) { blocked = true; }

    if (blocked) {
      console.log('  blocked at ' + zip + ' (' + i + '/' + todo.length + ' done) — cooling 75s...');
      sinceBreak = 0;
      await sleep(PAUSE);
      continue; // retry same zip
    }
    if (sinceBreak >= BATCH && i < todo.length) {
      console.log('  ' + i + '/' + todo.length + ' done — cooldown 75s...');
      sinceBreak = 0;
      await sleep(PAUSE);
    } else {
      await sleep(1200);
    }
  }
  const payload = JSON.stringify(out, null, 2);
  const blob = new Blob([payload], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'usps_metro.json';
  a.click();
  const okc = Object.values(out).filter(v => v && v.resultStatus === 'SUCCESS').length;
  console.log('=== DONE: ' + okc + '/' + zips.length + '. Downloaded usps_metro.json. ' +
              (okc < zips.length ? 'RE-RUN to finish the rest.' : 'Complete!'));
})();
