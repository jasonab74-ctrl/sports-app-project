(async function () {
  const LIST_EL = document.getElementById("story-list");
  const EMPTY_EL = document.getElementById("empty-state");
  const UPDATED_EL = document.getElementById("updated-at");

  function fmtDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString(undefined,{month:"short",day:"numeric"});
    } catch { return ""; }
  }
  function fmtTimeNow() {
    const d = new Date();
    return d.toLocaleTimeString(undefined,{hour:"numeric",minute:"2-digit"});
  }

  try {
    const resp = await fetch("static/teams/purdue-mbb/items.json",{cache:"no-cache"});
    const data = await resp.json();
    const items = Array.isArray(data.items)?data.items:[];
    UPDATED_EL.textContent = `Last updated ${fmtTimeNow()}`;

    if(!items.length){
      EMPTY_EL.hidden = false;
      LIST_EL.innerHTML = "";
      return;
    }

    EMPTY_EL.hidden = true;
    LIST_EL.innerHTML = "";

    items.forEach(item=>{
      const li=document.createElement("li");
      li.className="story-item";

      const src=document.createElement("div");
      src.className="story-source";
      src.textContent=item.source||"Unknown";

      const a=document.createElement("a");
      a.className="story-title";
      a.href=item.link;
      a.target="_blank";
      a.rel="noopener noreferrer";
      a.textContent=item.title||"(no title)";

      const when=document.createElement("div");
      when.className="story-date";
      when.textContent=fmtDate(item.date);

      li.appendChild(src);
      li.appendChild(a);
      li.appendChild(when);

      LIST_EL.appendChild(li);
    });

  } catch(err){
    console.error("render error",err);
    UPDATED_EL.textContent = `Last updated ${fmtTimeNow()}`;
    EMPTY_EL.hidden=false;
    LIST_EL.innerHTML="";
  }
})();