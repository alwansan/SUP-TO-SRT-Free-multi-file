const $=id=>document.getElementById(id);
const state={token:"",repo:"",files:[],job:null,running:false};

function log(s){$("log").textContent += s+"\n"; $("log").scrollTop=$("log").scrollHeight}
function setStatus(s,ok=null){$("connection").textContent=s;$("connection").style.color=ok===true?"#4ade80":ok===false?"#f87171":"#94a3b8"}
function headers(){return {"Accept":"application/vnd.github+json","Authorization":"Bearer "+state.token,"X-GitHub-Api-Version":"2026-03-10","Content-Type":"application/json"}}
async function api(path,opts={}){
  const r=await fetch("https://api.github.com"+path,{...opts,headers:{...headers(),...(opts.headers||{})}});
  let data=null; try{data=await r.json()}catch{}
  if(!r.ok) throw new Error((data&&data.message)||`${r.status} ${r.statusText}`);
  return data;
}
function repoParts(){
  const x=state.repo.trim().replace(/^https?:\/\/github\.com\//,"").replace(/\/$/,"").split("/");
  if(x.length!==2) throw Error("Repository must be owner/repository");
  return x;
}
function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}
function safeName(n){return n.replace(/[^A-Za-z0-9._ -]/g,"_").replace(/^\.|\.\.$/g,"_")}
function sleep(ms){return new Promise(r=>setTimeout(r,ms))}
function setProgress(n,t){$("bar").style.width=n+"%";$("progressText").textContent=t}
function readBase64(file){
  return new Promise((resolve,reject)=>{
    const r=new FileReader();
    r.onload=()=>resolve(String(r.result).split(",")[1]);
    r.onerror=reject;
    r.readAsDataURL(file);
  });
}

$("files").addEventListener("change",e=>{
  state.files=[...e.target.files].filter(f=>/\.sup$/i.test(f.name));
  renderFiles();
});
function renderFiles(){
  const box=$("fileList"); box.innerHTML="";
  if(!state.files.length){box.innerHTML='<div class="muted">No files selected.</div>';return}
  state.files.forEach((f,i)=>{
    const d=document.createElement("div");d.className="file";
    d.innerHTML=`<span>${i+1}. ${escapeHtml(f.name)}</span><small>${(f.size/1048576).toFixed(2)} MB</small>`;
    box.appendChild(d);
  });
}
$("dropzone").addEventListener("dragover",e=>{e.preventDefault()});
$("dropzone").addEventListener("drop",e=>{
  e.preventDefault();
  state.files=[...e.dataTransfer.files].filter(f=>/\.sup$/i.test(f.name));
  renderFiles();
});

$("test").onclick=async()=>{
  try{
    state.token=$("token").value.trim();state.repo=$("repo").value.trim();
    const [o,r]=repoParts();
    const d=await api(`/repos/${encodeURIComponent(o)}/${encodeURIComponent(r)}`);
    setStatus(`Connected: ${d.full_name} (${d.default_branch})`,true);
  }catch(e){setStatus(e.message,false)}
};

$("start").onclick=async()=>{
 if(state.running)return;
 let owner,repo,branch,run;
 try{
  state.token=$("token").value.trim();state.repo=$("repo").value.trim();
  [owner,repo]=repoParts();
  if(!state.token)throw Error("Enter a GitHub token.");
  if(!state.files.length)throw Error("Select at least one .sup file.");
  if(state.files.length>100)throw Error("Maximum 100 files per job.");
  for(const f of state.files)if(f.size>100*1024*1024)throw Error(`${f.name} is larger than 100 MB.`);

  state.running=true;$("start").disabled=true;$("progressWrap").classList.remove("hidden");
  $("download").classList.add("hidden");$("runLink").classList.add("hidden");$("log").textContent="";
  setProgress(1,"Checking repository…");

  const repoInfo=await api(`/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`);
  const base=repoInfo.default_branch;
  const baseRef=await api(`/repos/${owner}/${repo}/git/ref/heads/${encodeURIComponent(base)}`);
  const baseCommit=await api(`/repos/${owner}/${repo}/git/commits/${baseRef.object.sha}`);

  const job=crypto.randomUUID();state.job=job;branch=`jobs/${job}`;
  log(`Job: ${job}`);
  log(`Uploading ${state.files.length} SUP files…`);

  const blobs=[];
  for(let i=0;i<state.files.length;i++){
    const f=state.files[i];
    const b64=await readBase64(f);
    const blob=await api(`/repos/${owner}/${repo}/git/blobs`,{
      method:"POST",
      body:JSON.stringify({content:b64,encoding:"base64"})
    });
    blobs.push({path:`jobs/${job}/${safeName(f.name)}`,mode:"100644",type:"blob",sha:blob.sha});
    setProgress(5+Math.round((i+1)/state.files.length*42),`Uploaded ${i+1}/${state.files.length}`);
  }

  const tree=await api(`/repos/${owner}/${repo}/git/trees`,{
    method:"POST",
    body:JSON.stringify({base_tree:baseCommit.tree.sha,tree:blobs})
  });
  const commit=await api(`/repos/${owner}/${repo}/git/commits`,{
    method:"POST",
    body:JSON.stringify({message:`Temporary subtitle job ${job}`,tree:tree.sha,parents:[baseCommit.sha]})
  });
  await api(`/repos/${owner}/${repo}/git/refs`,{
    method:"POST",
    body:JSON.stringify({ref:`refs/heads/${branch}`,sha:commit.sha})
  });

  const inputs={
    job_id:job,
    clean:String($("clean").checked),
    remove_sounds:String($("sounds").checked),
    remove_names:String($("names").checked),
    remove_duplicates:String($("duplicates").checked),
    fix_ocr:String($("fixocr").checked)
  };
  await api(`/repos/${owner}/${repo}/actions/workflows/convert.yml/dispatches`,{
    method:"POST",body:JSON.stringify({ref:branch,inputs})
  });

  log("GitHub Actions started. OCR can take several minutes.");
  setProgress(50,"Waiting for runner…");
  run=await waitForRun(owner,repo,branch);
  $("runLink").href=run.html_url;$("runLink").classList.remove("hidden");

  if(run.conclusion!=="success")throw Error(`Workflow ended with ${run.conclusion||"failure"}. Open the run for logs.`);

  setProgress(92,"Preparing ZIP download…");
  const arts=await api(`/repos/${owner}/${repo}/actions/runs/${run.id}/artifacts`);
  const artifact=arts.artifacts.find(a=>a.name==="subtitle-result");
  if(!artifact)throw Error("Result artifact was not found.");

  try{
    const resp=await fetch(`https://api.github.com/repos/${owner}/${repo}/actions/artifacts/${artifact.id}/zip`,{
      headers:{
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+state.token,
        "X-GitHub-Api-Version":"2026-03-10"
      }
    });
    if(!resp.ok)throw Error("Direct artifact download failed.");
    const blob=await resp.blob();
    const url=URL.createObjectURL(blob);
    const a=$("download");
    a.href=url;a.download=`subtitles-${job}.zip`;a.textContent="⬇️ Download ZIP";a.classList.remove("hidden");
    a.onclick=()=>setTimeout(()=>URL.revokeObjectURL(url),60000);
    log("✅ Finished. The generated SRT files are packaged in the ZIP.");
  }catch(e){
    $("download").href=run.html_url;$("download").target="_blank";$("download").textContent="⬇️ Open run / download ZIP";$("download").classList.remove("hidden");
    log("✅ Finished. Direct download was blocked by the browser; use the run link to download the artifact ZIP.");
  }
  setProgress(100,"Done");
 }catch(e){
  log("❌ "+e.message);setProgress(0,"Failed");
 }finally{
  state.running=false;$("start").disabled=false;
 }
};

async function waitForRun(owner,repo,branch){
 for(let i=0;i<240;i++){
  const d=await api(`/repos/${owner}/${repo}/actions/runs?event=workflow_dispatch&branch=${encodeURIComponent(branch)}&per_page=20`);
  if(d.workflow_runs&&d.workflow_runs.length){
    const run=d.workflow_runs.find(x=>x.path.endsWith("/convert.yml"));
    if(run){
      if(run.status==="completed")return run;
      setProgress(50+Math.min(40,Math.floor(i/3)),`Processing… ${run.status}`);
    }
  }
  await sleep(5000);
 }
 throw Error("Timed out waiting for GitHub Actions.");
}
renderFiles();
