#!/usr/bin/env python3
"""Build the PWIS Executive Dashboard — self-contained HTML with embedded data.
Map-first layout, interactive sliders on every panel."""

import pandas as pd, json, os
os.chdir('/sessions/happy-wonderful-hawking/boise-pwis')

sewer = pd.read_csv('data/sewer_segments.csv')
geo = pd.read_csv('data/geothermal_segments.csv')
pi = pd.read_csv('data/pi_segments.csv')

def prep(df, cols):
    out = df[cols].copy()
    for c in out.columns:
        if out[c].dtype == bool:
            out[c] = out[c].astype(str)
    return out.to_dict('records')

sewer_cols = ['segment_id','corridor_name','district','pipe_class','pipe_material',
              'diameter_inches','length_ft','install_year','asset_age_years',
              'condition_score','breaks_last_5yr','capacity_utilization_pct',
              'ii_risk_flag','criticality_class','estimated_replacement_cost_usd','lat','lon']
geo_cols = ['segment_id','corridor_name','district','pipe_role','pipe_material',
            'diameter_inches','length_ft','install_year','asset_age_years',
            'condition_score','breaks_last_5yr','supply_temp_f','return_temp_f',
            'capacity_utilization_pct','criticality_class','estimated_replacement_cost_usd','lat','lon']
pi_cols = ['segment_id','subdivision','district','canal_source','pipe_material',
           'diameter_inches','length_ft','install_year','asset_age_years',
           'condition_score','breaks_last_5yr','capacity_utilization_pct',
           'operating_pressure_psi','criticality_class','estimated_replacement_cost_usd','lat','lon']

sj = json.dumps(prep(sewer, sewer_cols))
gj = json.dumps(prep(geo, geo_cols))
pj = json.dumps(prep(pi, pi_cols))

html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Boise PWIS Executive Dashboard</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
/* City of Boise brand: navy #003d5e, clean municipal feel */
:root{--navy:#003d5e;--navy-lt:#00526e;--navy-dk:#002a42;--bg:#f5f7fa;--sf:#ffffff;--sf2:#eef1f5;--br:#d1d8e0;--tx:#1a2b3c;--dm:#5a6d7e;--ac:#003d5e;--cr:#c0392b;--hi:#d4850a;--md:#2874a6;--lo:#1e8449;--sew:#2e5eaa;--geo:#c0392b;--pi:#1e8449}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--tx)}
.hdr{background:var(--navy);padding:14px 28px;display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid var(--navy-dk)}
.hdr h1{font-size:18px;font-weight:600;color:#fff}.hdr h1 em{color:#7ec8e3;font-style:normal}
.hdr-sub{font-size:11px;color:rgba(255,255,255,.7);margin-top:2px}
.hdr-r{text-align:right;font-size:10px;color:rgba(255,255,255,.6)}
.tabs{display:flex;background:#fff;border-bottom:2px solid var(--br);padding:0 20px}
.tab{padding:12px 24px;cursor:pointer;font-size:13px;font-weight:600;color:var(--dm);border-bottom:3px solid transparent;transition:all .15s;user-select:none}
.tab:hover{color:var(--tx);background:var(--sf2)}.tab.on{color:var(--tx)}
.tab[data-t="map"].on{border-color:var(--navy)}
.tab[data-t="sewer"].on{border-color:var(--sew)}
.tab[data-t="geo"].on{border-color:var(--geo)}
.tab[data-t="pi"].on{border-color:var(--pi)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}
.pnl{display:none;padding:22px 26px}.pnl.on{display:block}
.krow{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:20px}
.kc{background:#fff;border:1px solid var(--br);border-radius:8px;padding:16px 18px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.kc .lb{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--dm);margin-bottom:4px}
.kc .v{font-size:26px;font-weight:700;line-height:1.1}
.kc .s{font-size:10px;color:var(--dm);margin-top:3px}
.v.crit{color:var(--cr)}.v.warn{color:var(--hi)}.v.ok{color:var(--lo)}.v.bl{color:var(--navy)}
.st{font-size:15px;font-weight:600;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--br);color:var(--navy)}
.callout{border-radius:8px;padding:18px 22px;margin-bottom:20px}
.callout.danger{background:#fef2f2;border:1px solid #fecaca}
.callout.good{background:#f0fdf4;border:1px solid #bbf7d0}
.callout h3{font-size:14px;margin-bottom:5px}
.callout p{font-size:12px;color:var(--dm);line-height:1.55}
.callout .big{font-size:32px;font-weight:700}
.tbar{display:flex;height:34px;border-radius:5px;overflow:hidden;margin-bottom:5px}
.tbar div{display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:600;color:#fff;min-width:24px}
.tleg{display:flex;gap:14px;font-size:10px;color:var(--dm);margin-bottom:18px}
.tleg span{display:flex;align-items:center;gap:3px}
.tleg .sq{width:9px;height:9px;border-radius:2px}
.cgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}
.cbox{background:#fff;border:1px solid var(--br);border-radius:8px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.cbox h3{font-size:11px;color:var(--dm);text-transform:uppercase;letter-spacing:.4px;margin-bottom:10px}
.cbox canvas{width:100%!important}
.tw{max-height:380px;overflow-y:auto;border:1px solid var(--br);border-radius:7px;margin-bottom:20px}
.dt{width:100%;border-collapse:collapse;font-size:11px}
.dt th{text-align:left;padding:8px 10px;background:var(--navy);color:#fff;font-weight:600;text-transform:uppercase;letter-spacing:.4px;font-size:9px;border-bottom:2px solid var(--navy-dk);position:sticky;top:0}
.dt td{padding:7px 10px;border-bottom:1px solid var(--br)}
.dt tr:hover td{background:var(--sf2)}
.bg{padding:2px 7px;border-radius:3px;font-size:9px;font-weight:600}
.bg-c{background:rgba(192,57,43,.12);color:#c0392b}
.bg-p{background:rgba(212,133,10,.12);color:#b8860b}
.bg-f{background:rgba(40,116,166,.12);color:#2874a6}
.bg-g{background:rgba(30,132,73,.12);color:#1e8449}
#mapc{height:calc(100vh - 200px);border-radius:8px;border:1px solid var(--br)}
.lctrl{position:absolute;top:10px;right:10px;z-index:1000;background:rgba(255,255,255,.95);border:1px solid var(--br);border-radius:8px;padding:12px 16px;box-shadow:0 2px 8px rgba(0,0,0,.12)}
.lctrl h4{font-size:10px;color:var(--navy);text-transform:uppercase;margin-bottom:6px;font-weight:700}
.lcb{display:flex;align-items:center;gap:6px;margin-bottom:5px;cursor:pointer;font-size:12px;color:var(--tx)}
.lcb input[type=checkbox]{accent-color:var(--navy)}
.lcnt{font-size:9px;color:var(--dm);margin-left:auto}
.lsw{width:11px;height:11px;border-radius:2px;display:inline-block}
/* Slider controls */
.ctrl-bar{background:#fff;border:1px solid var(--br);border-radius:8px;padding:14px 20px;margin-bottom:18px;display:flex;flex-wrap:wrap;gap:18px;align-items:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.ctrl-bar.map-bar{background:#fff;border:1px solid var(--br);border-radius:8px;padding:12px 20px;margin-bottom:10px;display:flex;flex-wrap:wrap;gap:16px;align-items:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.ctrl-grp{display:flex;flex-direction:column;gap:3px;min-width:140px}
.ctrl-grp label{font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--dm);font-weight:600}
.ctrl-grp .ctrl-val{font-size:12px;font-weight:600;color:var(--navy);min-width:50px;text-align:right}
.ctrl-grp .ctrl-row{display:flex;align-items:center;gap:8px}
.ctrl-grp input[type=range]{flex:1;accent-color:var(--navy);height:4px;cursor:pointer;min-width:100px}
.ctrl-grp select{background:#fff;color:var(--tx);border:1px solid var(--br);border-radius:4px;padding:4px 8px;font-size:11px;cursor:pointer}
.ctrl-sep{width:1px;height:36px;background:var(--br)}
@media(max-width:900px){.cgrid{grid-template-columns:1fr}.krow{grid-template-columns:1fr 1fr}.ctrl-bar{gap:10px}}
</style>
</head>
<body>
<div class="hdr">
  <div><h1><em>BOISE</em> PUBLIC WORKS INTELLIGENCE SYSTEM</h1><div class="hdr-sub">Executive Infrastructure Dashboard</div></div>
  <div class="hdr-r">City of Boise &middot; Public Works<br>Portfolio Project &middot; Synthetic Data</div>
</div>
<div class="tabs">
  <div class="tab on" data-t="map" onclick="go('map')"><span class="dot" style="background:var(--ac)"></span>System Map</div>
  <div class="tab" data-t="sewer" onclick="go('sewer')"><span class="dot" style="background:var(--sew)"></span>Wastewater / Sewer</div>
  <div class="tab" data-t="geo" onclick="go('geo')"><span class="dot" style="background:var(--geo)"></span>Geothermal Heating</div>
  <div class="tab" data-t="pi" onclick="go('pi')"><span class="dot" style="background:var(--pi)"></span>Pressurized Irrigation</div>
</div>

<!-- MAP PANEL (first) -->
<div class="pnl on" id="p-map">
  <div class="ctrl-bar map-bar">
    <div class="ctrl-grp"><label>Min Age (yrs)</label><div class="ctrl-row"><input type="range" id="map-agemin" min="0" max="120" value="0" oninput="updMapFilters()"><span class="ctrl-val" id="map-agemin-v">0</span></div></div>
    <div class="ctrl-sep"></div>
    <div class="ctrl-grp"><label>Max Age (yrs)</label><div class="ctrl-row"><input type="range" id="map-age" min="0" max="120" value="120" oninput="updMapFilters()"><span class="ctrl-val" id="map-age-v">All</span></div></div>
    <div class="ctrl-sep"></div>
    <div class="ctrl-grp"><label>Min Condition</label><div class="ctrl-row"><input type="range" id="map-cond" min="0" max="100" value="0" oninput="updMapFilters()"><span class="ctrl-val" id="map-cond-v">0</span></div></div>
    <div class="ctrl-sep"></div>
    <div class="ctrl-grp"><label>Max Condition</label><div class="ctrl-row"><input type="range" id="map-condhi" min="0" max="100" value="100" oninput="updMapFilters()"><span class="ctrl-val" id="map-condhi-v">100</span></div></div>
    <div class="ctrl-sep"></div>
    <div class="ctrl-grp"><label>District</label><select id="map-dist" onchange="updMapFilters()"><option value="all">All Districts</option></select></div>
    <div class="ctrl-sep"></div>
    <div class="ctrl-grp"><label>Replacement Rate (%/yr)</label><div class="ctrl-row"><input type="range" id="map-rr" min="0.5" max="5" value="1.5" step="0.1" oninput="updMapKPI()"><span class="ctrl-val" id="map-rr-v">1.5%</span></div></div>
    <div class="ctrl-sep"></div>
    <div class="ctrl-grp"><label>Annual Budget ($M)</label><div class="ctrl-row"><input type="range" id="map-bud" min="1" max="200" value="50" step="1" oninput="updMapKPI()"><span class="ctrl-val" id="map-bud-v">$50M</span></div></div>
  </div>
  <div class="krow" id="map-kpis"></div>
  <div style="position:relative"><div id="mapc"></div>
    <div class="lctrl" id="lctrl">
      <h4>System Layers</h4>
      <label class="lcb"><input type="checkbox" checked data-ly="sewer" onchange="updMapFilters()"><span class="lsw" style="background:#2e5eaa"></span> Wastewater <span class="lcnt" id="cnt-sewer"></span></label>
      <label class="lcb"><input type="checkbox" checked data-ly="geo" onchange="updMapFilters()"><span class="lsw" style="background:#c0392b"></span> Geothermal <span class="lcnt" id="cnt-geo"></span></label>
      <label class="lcb"><input type="checkbox" checked data-ly="pi" onchange="updMapFilters()"><span class="lsw" style="background:#1e8449"></span> Pressurized Irrigation <span class="lcnt" id="cnt-pi"></span></label>
    </div>
  </div>
</div>

<div class="pnl" id="p-sewer"></div>
<div class="pnl" id="p-geo"></div>
<div class="pnl" id="p-pi"></div>

<script>
const D={sewer:''' + sj + ''',geo:''' + gj + ''',pi:''' + pj + '''};

const F=n=>n.toLocaleString('en-US');
const FM=n=>'$'+(n/1e6).toFixed(1)+'M';
const FK=n=>n>=1e6?FM(n):n>=1000?'$'+(n/1000).toFixed(0)+'K':'$'+F(n);
const MI=ft=>(ft/5280).toFixed(1);
const PCT=(n,d)=>d>0?(n/d*100).toFixed(1)+'%':'0%';
function tier(c){return c<30?'critical':c<50?'poor':c<70?'fair':'good'}
function tierC(t){return{critical:'#c0392b',poor:'#d4850a',fair:'#2874a6',good:'#1e8449'}[t]}

let mapReady=false;
function go(t){
  document.querySelectorAll('.tab').forEach(e=>e.classList.remove('on'));
  document.querySelector(`.tab[data-t="${t}"]`).classList.add('on');
  document.querySelectorAll('.pnl').forEach(e=>e.classList.remove('on'));
  document.getElementById('p-'+t).classList.add('on');
  if(t==='map'&&!mapReady){setTimeout(initMap,80);mapReady=true}
  // Redraw charts when switching to a system panel (canvas sizing)
  if(t!=='map'&&panels[t]){setTimeout(()=>panels[t].redraw(),60)}
}

/* ═══════════════════════════════════════════════
   SYSTEM PANEL BUILDER (with sliders)
   ═══════════════════════════════════════════════ */
const panels={};
function refreshPanel(el){var pid=el.getAttribute('data-panel');if(panels[pid])panels[pid].refresh()}

function buildPanel(id,allData,cfg){
  const el=document.getElementById('p-'+id);
  const dists=[...new Set(allData.map(d=>d.district))].sort();
  const maxDataAge=Math.max(...allData.map(function(d){return d.asset_age_years}));

  // Build system-specific control bar
  function sl(){return ' oninput="refreshPanel(this)" data-panel="'+id+'"'}
  function sc(){return ' onchange="refreshPanel(this)" data-panel="'+id+'"'}
  let distOpts=dists.map(function(d){return '<option value="'+d+'">'+d+'</option>'}).join('');

  var ctrl='<div class="ctrl-bar" id="ctrl-'+id+'">';

  // All systems get age range (min + max) and district
  ctrl+='<div class="ctrl-grp"><label>Min Age (yrs)</label><div class="ctrl-row"><input type="range" id="'+id+'-agemin" min="0" max="'+Math.ceil(maxDataAge)+'" value="0"'+sl()+'><span class="ctrl-val" id="'+id+'-agemin-v">0</span></div></div>';
  ctrl+='<div class="ctrl-sep"></div>';
  ctrl+='<div class="ctrl-grp"><label>Max Age (yrs)</label><div class="ctrl-row"><input type="range" id="'+id+'-agemax" min="0" max="'+Math.ceil(maxDataAge)+'" value="'+Math.ceil(maxDataAge)+'"'+sl()+'><span class="ctrl-val" id="'+id+'-agemax-v">All</span></div></div>';
  ctrl+='<div class="ctrl-sep"></div>';
  ctrl+='<div class="ctrl-grp"><label>District</label><select id="'+id+'-dist"'+sc()+'>'+('<option value="all">All</option>'+distOpts)+'</select></div>';

  // Sewer gets replacement rate + budget (capital investment story)
  if(id==='sewer'){
    ctrl+='<div class="ctrl-sep"></div>';
    ctrl+='<div class="ctrl-grp"><label>Replacement Rate (%/yr)</label><div class="ctrl-row"><input type="range" id="'+id+'-rr" min="0.5" max="5" value="1.5" step="0.1"'+sl()+'><span class="ctrl-val" id="'+id+'-rr-v">1.5%</span></div></div>';
    ctrl+='<div class="ctrl-sep"></div>';
    ctrl+='<div class="ctrl-grp"><label>Annual CIP Budget ($M)</label><div class="ctrl-row"><input type="range" id="'+id+'-bud" min="5" max="200" value="50" step="1"'+sl()+'><span class="ctrl-val" id="'+id+'-bud-v">$50M</span></div></div>';
  }

  // Geothermal gets pipe role filter
  if(id==='geo'){
    var roles=[...new Set(allData.map(function(d){return d.pipe_role}))].sort();
    var roleOpts=roles.map(function(r){return '<option value="'+r+'">'+r.replace(/_/g," ")+'</option>'}).join('');
    ctrl+='<div class="ctrl-sep"></div>';
    ctrl+='<div class="ctrl-grp"><label>Pipe Role</label><select id="'+id+'-role"'+sc()+'>'+('<option value="all">All Roles</option>'+roleOpts)+'</select></div>';
  }

  // PI gets subdivision and canal source filters
  if(id==='pi'){
    var subs=[...new Set(allData.map(function(d){return d.subdivision}))].sort();
    var subOpts=subs.map(function(s){return '<option value="'+s+'">'+s+'</option>'}).join('');
    ctrl+='<div class="ctrl-sep"></div>';
    ctrl+='<div class="ctrl-grp"><label>Subdivision</label><select id="'+id+'-sub"'+sc()+'>'+('<option value="all">All Subdivisions</option>'+subOpts)+'</select></div>';
    var canals=[...new Set(allData.map(function(d){return d.canal_source}))].sort();
    var canalOpts=canals.map(function(c){return '<option value="'+c+'">'+c+'</option>'}).join('');
    ctrl+='<div class="ctrl-sep"></div>';
    ctrl+='<div class="ctrl-grp"><label>Canal Source</label><select id="'+id+'-canal"'+sc()+'>'+('<option value="all">All Canals</option>'+canalOpts)+'</select></div>';
  }

  ctrl+='</div>';
  el.innerHTML = ctrl + '<div id="body-'+id+'"></div>';

  function refresh(){
    var ageMin=+document.getElementById(id+'-agemin').value;
    var ageMax=+document.getElementById(id+'-agemax').value;
    var distF=document.getElementById(id+'-dist').value;

    document.getElementById(id+'-agemin-v').textContent=ageMin;
    document.getElementById(id+'-agemax-v').textContent=ageMax>=maxDataAge?'All':'≤'+ageMax;

    // System-specific slider reads
    var rr=1.5, budget=50e6;
    if(id==='sewer'){
      rr=+document.getElementById(id+'-rr').value;
      budget=+document.getElementById(id+'-bud').value*1e6;
      document.getElementById(id+'-rr-v').textContent=rr.toFixed(1)+'%';
      document.getElementById(id+'-bud-v').textContent='$'+document.getElementById(id+'-bud').value+'M';
    }

    var data=allData;
    data=data.filter(function(d){return d.asset_age_years>=ageMin && d.asset_age_years<=ageMax});
    if(distF!=='all') data=data.filter(function(d){return d.district===distF});

    // Geothermal role filter
    if(id==='geo'){
      var roleF=document.getElementById(id+'-role').value;
      if(roleF!=='all') data=data.filter(function(d){return d.pipe_role===roleF});
    }

    // PI subdivision + canal filters
    if(id==='pi'){
      var subF=document.getElementById(id+'-sub').value;
      var canalF=document.getElementById(id+'-canal').value;
      if(subF!=='all') data=data.filter(function(d){return d.subdivision===subF});
      if(canalF!=='all') data=data.filter(function(d){return d.canal_source===canalF});
    }

    if(data.length===0){document.getElementById('body-'+id).innerHTML='<p style="padding:40px;color:var(--dm)">No segments match current filters.</p>';return}

    renderBody(id,data,cfg,rr,budget);
  }

  function redraw(){refresh()}
  panels[id]={refresh,redraw};
  refresh();
}

function renderBody(id,data,cfg,rr,budget){
  const body=document.getElementById('body-'+id);
  const tot=data.reduce((s,d)=>s+d.length_ft,0);
  const totCost=data.reduce((s,d)=>s+d.estimated_replacement_cost_usd,0);
  const avgC=data.reduce((s,d)=>s+d.condition_score,0)/data.length;
  const avgA=data.reduce((s,d)=>s+d.asset_age_years,0)/data.length;

  // Fixed tier thresholds
  const CT=30;
  const crit=[],poor=[],fair=[],good=[];
  data.forEach(d=>{
    if(d.condition_score<CT)crit.push(d);
    else if(d.condition_score<50)poor.push(d);
    else if(d.condition_score<70)fair.push(d);
    else good.push(d);
  });

  const critL=crit.reduce((s,d)=>s+d.length_ft,0);
  const critC=crit.reduce((s,d)=>s+d.estimated_replacement_cost_usd,0);
  const pctCrit=(crit.length/data.length*100).toFixed(1);

  let h='';

  // KPIs — system-specific
  h+=`<div class="krow">
    <div class="kc"><div class="lb">Network</div><div class="v bl">${MI(tot)} mi</div><div class="s">${F(data.length)} segments</div></div>
    <div class="kc"><div class="lb">Avg Condition</div><div class="v ${avgC<30?'crit':avgC<50?'warn':'ok'}">${avgC.toFixed(0)}<span style="font-size:13px;color:var(--dm)"> / 100</span></div><div class="s">Avg age: ${avgA.toFixed(0)} yrs</div></div>
    <div class="kc"><div class="lb">Critical (&lt;30)</div><div class="v ${parseFloat(pctCrit)>3?'crit':'ok'}">${pctCrit}%</div><div class="s">${F(crit.length)} segs &middot; ${MI(critL)} mi</div></div>`;

  if(id==='sewer'){
    // Sewer: capital replacement story
    const ssAnnualFt=tot*(rr/100);
    const backlogYrs=critL>0?critL/ssAnnualFt:0;
    const annCostNeeded=backlogYrs>0?critC/backlogYrs:0;
    const budgetYrs=critC>0?critC/budget:0;
    h+=`<div class="kc"><div class="lb">Backlog Cost</div><div class="v crit">${FM(critC)}</div><div class="s">${MI(critL)} mi needs action</div></div>
    <div class="kc"><div class="lb">Yrs to Clear at ${rr}%/yr</div><div class="v ${backlogYrs>5?'warn':backlogYrs>0?'bl':'ok'}">${backlogYrs>0?backlogYrs.toFixed(1):'&mdash;'}</div><div class="s">${MI(ssAnnualFt)} mi/yr replacement</div></div>
    <div class="kc"><div class="lb">Budget Gap</div><div class="v ${annCostNeeded>budget?'crit':'ok'}">${annCostNeeded>budget?FM(annCostNeeded-budget):'None'}</div><div class="s">Need ${FM(annCostNeeded)}/yr vs ${FM(budget)} budget</div></div>`;
  } else if(id==='geo'){
    // Geothermal: temperature and operational
    const avgSup=data.reduce((s,d)=>s+(d.supply_temp_f||0),0)/data.length;
    const avgRet=data.reduce((s,d)=>s+(d.return_temp_f||0),0)/data.length;
    const deltaT=avgSup-avgRet;
    h+=`<div class="kc"><div class="lb">Avg Supply Temp</div><div class="v bl">${avgSup.toFixed(0)}&deg;F</div><div class="s">Target: 150&ndash;175&deg;F</div></div>
    <div class="kc"><div class="lb">Avg Return Temp</div><div class="v bl">${avgRet.toFixed(0)}&deg;F</div><div class="s">&Delta;T: ${deltaT.toFixed(0)}&deg;F</div></div>
    <div class="kc"><div class="lb">Replacement Value</div><div class="v bl">${FM(totCost)}</div><div class="s">Total system value</div></div>`;
  } else if(id==='pi'){
    // PI: pressure and seasonal
    const avgPSI=data.reduce((s,d)=>s+(d.operating_pressure_psi||0),0)/data.length;
    const nsub=[...new Set(data.map(d=>d.subdivision))].length;
    h+=`<div class="kc"><div class="lb">Avg Pressure</div><div class="v bl">${avgPSI.toFixed(0)} PSI</div><div class="s">Design: 80&ndash;115 PSI</div></div>
    <div class="kc"><div class="lb">Subdivisions</div><div class="v bl">${nsub}</div><div class="s">Active service areas</div></div>
    <div class="kc"><div class="lb">Replacement Value</div><div class="v bl">${FM(totCost)}</div><div class="s">Total system value</div></div>`;
  }
  h+=`</div>`;

  // Status callout
  const critGoal=3.0;
  if(parseFloat(pctCrit)>critGoal){
    h+=`<div class="callout danger"><h3>Above ${critGoal}% Critical Target</h3><p>Currently <strong>${pctCrit}%</strong> of the network (${MI(critL)} mi) is below condition 30.`;
    if(id==='sewer'){
      const ssAnnualFt=tot*(rr/100);const backlogYrs=critL>0?critL/ssAnnualFt:0;const budgetYrs=critC>0?critC/budget:0;
      h+=` At <strong>${rr}%/yr replacement</strong>, clearing the backlog takes <strong>${backlogYrs.toFixed(1)}</strong> years. With a <strong>${FM(budget)}/yr budget</strong>, it takes <strong>${budgetYrs.toFixed(1)} years</strong> to fund all critical replacements.`;
    }
    h+=`</p></div>`;
  } else if(parseFloat(pctCrit)>0){
    h+=`<div class="callout good"><h3>Near Target: ${pctCrit}% Critical (goal &lt;${critGoal}%)</h3><p><strong>${F(crit.length)}</strong> segments (${MI(critL)} mi) are below condition 30. Replacement backlog of <strong>${FM(critC)}</strong> is manageable.</p></div>`;
  } else {
    h+=`<div class="callout good"><h3>System Health: Excellent</h3><p>No segments below condition 30. Average condition ${avgC.toFixed(0)}/100, average age ${avgA.toFixed(0)} years.</p></div>`;
  }

  // Tier bar — fixed bands
  h+=`<div class="st">Condition Distribution</div><div class="tbar">
    <div style="width:${PCT(crit.length,data.length)};background:var(--cr)">${crit.length||''}</div>
    <div style="width:${PCT(poor.length,data.length)};background:var(--hi)">${poor.length||''}</div>
    <div style="width:${PCT(fair.length,data.length)};background:var(--md)">${fair.length||''}</div>
    <div style="width:${PCT(good.length,data.length)};background:var(--lo)">${good.length||''}</div>
  </div><div class="tleg">
    <span><span class="sq" style="background:var(--cr)"></span> Critical (&lt;30): ${F(crit.length)}</span>
    <span><span class="sq" style="background:var(--hi)"></span> Poor (30&ndash;49): ${F(poor.length)}</span>
    <span><span class="sq" style="background:var(--md)"></span> Fair (50&ndash;69): ${F(fair.length)}</span>
    <span><span class="sq" style="background:var(--lo)"></span> Good (70+): ${F(good.length)}</span>
  </div>`;

  // Charts
  h+=`<div class="cgrid">
    <div class="cbox"><h3>Segments by Install Decade</h3><canvas id="c-dec-${id}"></canvas></div>
    <div class="cbox"><h3>Network Length by Material (mi)</h3><canvas id="c-mat-${id}"></canvas></div>
    <div class="cbox"><h3>Condition by District</h3><canvas id="c-dist-${id}"></canvas></div>
    <div class="cbox"><h3>Replacement Cost by District</h3><canvas id="c-dc-${id}"></canvas></div>
  </div>`;

  // Top worst corridors
  const ck=cfg.ck||'corridor_name';
  const corrs={};
  crit.forEach(d=>{const nm=d[ck];if(!corrs[nm])corrs[nm]={n:0,l:0,c:0,w:100};corrs[nm].n++;corrs[nm].l+=d.length_ft;corrs[nm].c+=d.estimated_replacement_cost_usd;corrs[nm].w=Math.min(corrs[nm].w,d.condition_score)});
  const topC=Object.entries(corrs).sort((a,b)=>b[1].c-a[1].c).slice(0,10);
  if(topC.length>0){
    h+=`<div class="st">Top Critical ${cfg.cl}s &mdash; Highest Replacement Cost</div><div class="tw"><table class="dt"><thead><tr><th>#</th><th>${cfg.cl}</th><th>Segs</th><th>Length</th><th>Worst</th><th>Est. Cost</th></tr></thead><tbody>`;
    topC.forEach(([nm,d],i)=>{h+=`<tr><td>${i+1}</td><td><strong>${nm}</strong></td><td>${d.n}</td><td>${MI(d.l)} mi</td><td><span class="bg bg-c">${d.w}</span></td><td><strong>${FM(d.c)}</strong></td></tr>`});
    h+=`</tbody></table></div>`;
  }

  // System extras
  if(cfg.extra) h+=cfg.extra(data,{critical:crit,poor,fair,good});

  body.innerHTML=h;

  // Draw charts
  const mats={},matL={};
  data.forEach(d=>{mats[d.pipe_material]=(mats[d.pipe_material]||0)+1;matL[d.pipe_material]=(matL[d.pipe_material]||0)+d.length_ft});
  const decs={};
  data.forEach(d=>{const k=Math.floor(d.install_year/10)*10;if(!decs[k])decs[k]={n:0,l:0,cn:0};decs[k].n++;decs[k].l+=d.length_ft;if(d.condition_score<30)decs[k].cn++});
  const dists={};
  data.forEach(d=>{if(!dists[d.district])dists[d.district]={n:0,l:0,cn:0,c:0};dists[d.district].n++;dists[d.district].l+=d.length_ft;if(d.condition_score<30)dists[d.district].cn++;dists[d.district].c+=d.estimated_replacement_cost_usd});

  setTimeout(()=>{
    drawBars('c-dec-'+id,decs,cfg.color);
    drawHBars('c-mat-'+id,matL,cfg.color);
    drawDistBars('c-dist-'+id,dists);
    drawDistCost('c-dc-'+id,dists,cfg.color);
  },40);
}

/* ═══ CANVAS CHARTS ═══ */
function gctx(cid){const c=document.getElementById(cid);if(!c)return null;const dpr=window.devicePixelRatio||1;const rct=c.parentElement.getBoundingClientRect();c.width=rct.width*dpr;c.height=240*dpr;c.style.height='240px';const ctx=c.getContext('2d');ctx.scale(dpr,dpr);return{ctx,w:rct.width,h:240}}
function drawBars(cid,data,clr){const r=gctx(cid);if(!r)return;const{ctx,w,h}=r;const s=Object.entries(data).sort((a,b)=>+a[0]-+b[0]);if(!s.length)return;const mx=Math.max(...s.map(d=>d[1].n));const bw=Math.min(36,(w-56)/s.length-4);const L=48,T=8,bh=h-36;ctx.fillStyle='#5a6d7e';ctx.font='9px sans-serif';ctx.textAlign='right';for(let i=0;i<=4;i++){const y=T+bh-bh*i/4;ctx.fillText(F(Math.round(mx*i/4)),L-5,y+3);ctx.strokeStyle='rgba(0,0,0,.1)';ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(w-8,y);ctx.stroke()}s.forEach(([lb,d],i)=>{const x=L+i*((w-L-8)/s.length)+bw*.25;const bH=d.n/mx*bh;ctx.fillStyle=clr;ctx.fillRect(x,T+bh-bH,bw,bH);if(d.cn>0){ctx.fillStyle='#c0392b';const cH=d.cn/mx*bh;ctx.fillRect(x,T+bh-bH,bw,cH)}ctx.fillStyle='#5a6d7e';ctx.font='8px sans-serif';ctx.textAlign='center';ctx.fillText(lb+'s',x+bw/2,h-5)})}
function drawHBars(cid,data,clr){const r=gctx(cid);if(!r)return;const{ctx,w,h}=r;const s=Object.entries(data).sort((a,b)=>b[1]-a[1]);if(!s.length)return;const mx=s[0][1];const bH=Math.min(26,(h-16)/s.length-4);const lw=120;s.forEach(([lb,v],i)=>{const y=8+i*(bH+5);const bW=v/mx*(w-lw-55);ctx.fillStyle='#5a6d7e';ctx.font='10px sans-serif';ctx.textAlign='right';ctx.fillText(lb,lw-5,y+bH/2+4);ctx.fillStyle=clr;ctx.fillRect(lw,y,bW,bH);ctx.fillStyle='#1a2b3c';ctx.font='9px sans-serif';ctx.textAlign='left';ctx.fillText(MI(v)+' mi',lw+bW+5,y+bH/2+4)})}
function drawDistBars(cid,dists){const r=gctx(cid);if(!r)return;const{ctx,w,h}=r;const s=Object.entries(dists).sort((a,b)=>b[1].n-a[1].n);if(!s.length)return;const mx=Math.max(...s.map(d=>d[1].n));const bH=Math.min(28,(h-16)/s.length-4);const lw=90;s.forEach(([nm,d],i)=>{const y=8+i*(bH+5);const tw=d.n/mx*(w-lw-80);const cw=d.n>0?d.cn/d.n*tw:0;ctx.fillStyle='#5a6d7e';ctx.font='10px sans-serif';ctx.textAlign='right';ctx.fillText(nm,lw-5,y+bH/2+4);if(cw>0){ctx.fillStyle='#c0392b';ctx.fillRect(lw,y,cw,bH)}ctx.fillStyle='#2874a6';ctx.fillRect(lw+cw,y,tw-cw,bH);ctx.fillStyle='#1a2b3c';ctx.font='9px sans-serif';ctx.textAlign='left';const pct=d.n>0?(d.cn/d.n*100).toFixed(0):'0';ctx.fillText(d.n+' ('+pct+'% crit)',lw+tw+5,y+bH/2+4)})}
function drawDistCost(cid,dists,clr){const r=gctx(cid);if(!r)return;const{ctx,w,h}=r;const s=Object.entries(dists).sort((a,b)=>b[1].c-a[1].c);if(!s.length)return;const mx=s[0][1].c;const bH=Math.min(28,(h-16)/s.length-4);const lw=90;s.forEach(([nm,d],i)=>{const y=8+i*(bH+5);const bW=d.c/mx*(w-lw-70);ctx.fillStyle='#5a6d7e';ctx.font='10px sans-serif';ctx.textAlign='right';ctx.fillText(nm,lw-5,y+bH/2+4);ctx.fillStyle=clr;ctx.fillRect(lw,y,bW,bH);ctx.fillStyle='#1a2b3c';ctx.font='9px sans-serif';ctx.textAlign='left';ctx.fillText(FM(d.c),lw+bW+5,y+bH/2+4)})}

/* ═══ SYSTEM EXTRAS ═══ */
function sewerExtra(data,tiers){
  const cls={};
  data.forEach(d=>{if(!cls[d.pipe_class])cls[d.pipe_class]={n:0,l:0,cn:0};cls[d.pipe_class].n++;cls[d.pipe_class].l+=d.length_ft;if(d.condition_score<30)cls[d.pipe_class].cn++});
  const ii=data.filter(d=>d.ii_risk_flag==='True');
  let h=`<div class="st">Sewer Network Breakdown</div><div class="krow">`;
  ['trunk','collector','lateral'].forEach(c=>{const d=cls[c]||{n:0,l:0,cn:0};h+=`<div class="kc"><div class="lb">${c} lines</div><div class="v bl">${MI(d.l)} mi</div><div class="s">${d.n} segs &middot; ${d.cn} critical</div></div>`});
  h+=`<div class="kc"><div class="lb">I&I Risk Flagged</div><div class="v warn">${F(ii.length)}</div><div class="s">${(ii.length/data.length*100).toFixed(1)}% of network</div></div></div>`;
  const ob=data.filter(d=>d.pipe_material==='Orangeburg');
  if(ob.length>0){const obc=ob.filter(d=>d.condition_score<30).length;h+=`<div class="callout danger"><h3>Orangeburg Pipe Alert</h3><p><strong>${ob.length}</strong> Orangeburg (tar-paper) segments remain. <strong>${obc}</strong> below condition 30. Highest failure rate &mdash; prioritize for full replacement.</p></div>`}
  return h;
}
function geoExtra(data,tiers){
  const roles={};
  data.forEach(d=>{if(!roles[d.pipe_role])roles[d.pipe_role]={n:0,l:0,ts:0,tr:0};roles[d.pipe_role].n++;roles[d.pipe_role].l+=d.length_ft;roles[d.pipe_role].ts+=(d.supply_temp_f||0);roles[d.pipe_role].tr+=(d.return_temp_f||0)});
  let h=`<div class="st">Pipeline Role Breakdown</div><div class="krow">`;
  Object.entries(roles).sort((a,b)=>b[1].l-a[1].l).forEach(([r,d])=>{h+=`<div class="kc"><div class="lb">${r.replace(/_/g,' ')}</div><div class="v bl">${MI(d.l)} mi</div><div class="s">${d.n} segs &middot; Sup: ${(d.ts/d.n).toFixed(0)}&deg;F &middot; Ret: ${(d.tr/d.n).toFixed(0)}&deg;F</div></div>`});
  h+=`</div>`;
  return h;
}
function piExtra(data,tiers){
  const subs={};
  data.forEach(d=>{const nm=d.subdivision;if(!subs[nm])subs[nm]={n:0,l:0,tc:0,tp:0,cs:d.canal_source};subs[nm].n++;subs[nm].l+=d.length_ft;subs[nm].tc+=d.condition_score;subs[nm].tp+=(d.operating_pressure_psi||0)});
  let h=`<div class="st">Subdivision Detail</div><div class="tw"><table class="dt"><thead><tr><th>Subdivision</th><th>Canal Source</th><th>Segs</th><th>Length</th><th>Avg Condition</th><th>Avg PSI</th></tr></thead><tbody>`;
  Object.entries(subs).sort((a,b)=>(a[1].tc/a[1].n)-(b[1].tc/b[1].n)).forEach(([nm,d])=>{const ac=(d.tc/d.n).toFixed(0);const cls=ac<30?'bg-c':ac<50?'bg-p':ac<70?'bg-f':'bg-g';h+=`<tr><td><strong>${nm}</strong></td><td>${d.cs}</td><td>${d.n}</td><td>${MI(d.l)} mi</td><td><span class="bg ${cls}">${ac}</span></td><td>${(d.tp/d.n).toFixed(0)}</td></tr>`});
  h+=`</tbody></table></div>`;return h;
}

/* ═══ MAP ═══ */
let mp,allMarkers=[];
function initMap(){
  mp=L.map('mapc').setView([43.615,-116.22],12);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{attribution:'OSM/CARTO',maxZoom:18}).addTo(mp);

  const sc={sewer:'#2e5eaa',geo:'#c0392b',pi:'#1e8449'};
  function addM(arr,sys,nk){
    arr.forEach(d=>{
      const tc=tierC(tier(d.condition_score));const rd=d.condition_score<30?5:d.condition_score<50?4:3;
      const m=L.circleMarker([d.lat,d.lon],{radius:rd,color:sc[sys],fillColor:tc,fillOpacity:.8,weight:1.5,opacity:.9});
      m.bindPopup(`<div style="font:12px sans-serif;min-width:170px"><strong style="color:${sc[sys]}">${d.segment_id}</strong><br><strong>${d[nk]}</strong> &middot; ${d.district}<br>${d.pipe_material} &middot; ${d.diameter_inches}&Prime;<br>Installed ${d.install_year} (${d.asset_age_years} yr)<br>Condition: <strong style="color:${tc}">${d.condition_score}</strong>/100<br>${F(d.length_ft)} ft &middot; $${F(d.estimated_replacement_cost_usd)}</div>`);
      allMarkers.push({m,sys,d});
    });
  }
  addM(D.sewer,'sewer','corridor_name');
  addM(D.geo,'geo','corridor_name');
  addM(D.pi,'pi','subdivision');

  // Populate district dropdown
  const allDists=[...new Set([...D.sewer,...D.geo,...D.pi].map(d=>d.district))].sort();
  const sel=document.getElementById('map-dist');
  allDists.forEach(d=>{const o=document.createElement('option');o.value=d;o.textContent=d;sel.appendChild(o)});

  document.getElementById('cnt-sewer').textContent=D.sewer.length;
  document.getElementById('cnt-geo').textContent=D.geo.length;
  document.getElementById('cnt-pi').textContent=D.pi.length;

  updMapFilters();
  // Force Leaflet to recalculate after container is fully rendered
  setTimeout(function(){mp.invalidateSize()},300);
}

function updMapFilters(){
  if(!mp)return;
  const minAge=+document.getElementById('map-agemin').value;
  const maxAge=+document.getElementById('map-age').value;
  const condLo=+document.getElementById('map-cond').value;
  const condHi=+document.getElementById('map-condhi').value;
  const dist=document.getElementById('map-dist').value;
  document.getElementById('map-agemin-v').textContent=minAge;
  document.getElementById('map-age-v').textContent=maxAge>=120?'All':'≤'+maxAge;
  document.getElementById('map-cond-v').textContent=condLo;
  document.getElementById('map-condhi-v').textContent=condHi;

  const sl={};
  document.querySelectorAll('#lctrl input[data-ly]').forEach(cb=>{sl[cb.dataset.ly]=cb.checked});

  let shown=0,hidden=0;
  allMarkers.forEach(({m,sys,d})=>{
    const vis = sl[sys]
      && d.asset_age_years>=minAge
      && d.asset_age_years<=maxAge
      && d.condition_score>=condLo
      && d.condition_score<=condHi
      && (dist==='all'||d.district===dist);
    if(vis){if(!mp.hasLayer(m))mp.addLayer(m);shown++}
    else{if(mp.hasLayer(m))mp.removeLayer(m);hidden++}
  });

  updMapKPI();
}

function updMapKPI(){
  const minAge=+document.getElementById('map-agemin').value;
  const maxAge=+document.getElementById('map-age').value;
  const condLo=+document.getElementById('map-cond').value;
  const condHi=+document.getElementById('map-condhi').value;
  const dist=document.getElementById('map-dist').value;
  const rr=+document.getElementById('map-rr').value;
  const budget=+document.getElementById('map-bud').value*1e6;
  document.getElementById('map-rr-v').textContent=rr.toFixed(1)+'%';
  document.getElementById('map-bud-v').textContent='$'+document.getElementById('map-bud').value+'M';

  const sl={};
  document.querySelectorAll('#lctrl input[data-ly]').forEach(cb=>{sl[cb.dataset.ly]=cb.checked});

  let segs=0,totL=0,critN=0,critL=0,critC=0,totC=0;
  allMarkers.forEach(({sys,d})=>{
    if(!sl[sys])return;
    if(d.asset_age_years<minAge||d.asset_age_years>maxAge)return;
    if(d.condition_score<condLo||d.condition_score>condHi)return;
    if(dist!=='all'&&d.district!==dist)return;
    segs++;totL+=d.length_ft;totC+=d.estimated_replacement_cost_usd;
    if(d.condition_score<30){critN++;critL+=d.length_ft;critC+=d.estimated_replacement_cost_usd}
  });

  const pctCrit=segs>0?(critN/segs*100).toFixed(1):'0.0';
  const ssAnnual=totL*(rr/100);
  const backlog=critL>0?critL/ssAnnual:0;
  const annCostNeeded=backlog>0?critC/backlog:0;
  const budgetYrs=critC>0?critC/budget:0;
  const budgetGap=annCostNeeded>budget?annCostNeeded-budget:0;

  document.getElementById('map-kpis').innerHTML=`
    <div class="kc"><div class="lb">Visible Segments</div><div class="v bl">${F(segs)}</div><div class="s">${MI(totL)} miles</div></div>
    <div class="kc"><div class="lb">Critical (&lt;30)</div><div class="v ${parseFloat(pctCrit)>3?'crit':'ok'}">${pctCrit}%</div><div class="s">${F(critN)} segs &middot; ${MI(critL)} mi</div></div>
    <div class="kc"><div class="lb">Backlog Cost</div><div class="v crit">${FM(critC)}</div><div class="s">Critical replacement total</div></div>
    <div class="kc"><div class="lb">Yrs to Clear at ${rr}%</div><div class="v ${backlog>5?'warn':backlog>0?'bl':'ok'}">${backlog>0?backlog.toFixed(1):'—'}</div><div class="s">${MI(ssAnnual)} mi/yr capacity</div></div>
    <div class="kc"><div class="lb">Budget: Yrs to Fund</div><div class="v ${budgetYrs>5?'warn':budgetYrs>0?'bl':'ok'}">${budgetYrs>0?budgetYrs.toFixed(1):'—'}</div><div class="s">${FM(budget)}/yr budget</div></div>
    <div class="kc"><div class="lb">Budget Gap</div><div class="v ${budgetGap>0?'crit':'ok'}">${budgetGap>0?FM(budgetGap):'None'}</div><div class="s">Need ${FM(annCostNeeded)}/yr vs ${FM(budget)}</div></div>`;
}

/* ═══ INIT ═══ */
// Script is at end of body — DOM is already parsed, init immediately
// Use short timeout so the browser has painted the map container
setTimeout(function(){
  initMap();
  mapReady=true;
}, 50);
buildPanel('sewer',D.sewer,{color:'#2e5eaa',ck:'corridor_name',cl:'Corridor',extra:sewerExtra});
buildPanel('geo',D.geo,{color:'#c0392b',ck:'corridor_name',cl:'Corridor',extra:geoExtra});
buildPanel('pi',D.pi,{color:'#1e8449',ck:'subdivision',cl:'Subdivision',extra:piExtra});
</script>
</body>
</html>'''

out = '/sessions/happy-wonderful-hawking/mnt/outputs/pwis-dashboard.html'
with open(out, 'w') as f:
    f.write(html)
print(f"Dashboard written: {os.path.getsize(out)/1e6:.1f} MB")
