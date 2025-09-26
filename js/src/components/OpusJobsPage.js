import React, { useEffect, useState } from "react";
import axios from "axios";
import { API_PREFIX } from "./index";

export default function OpusJobsPage(){
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(()=>{
    let mounted = true;
    const tick = async () => {
      try {
        const { data } = await axios.get(`${API_PREFIX}/opus/jobs`);
        if (mounted) setData(data);
      } catch(e){ setErr(e.response?.data?.detail || e.message); }
    };
    tick();
    const t = setInterval(tick, 5000);
    return ()=>{ mounted=false; clearInterval(t); };
  }, []);

  const items = data?.uws?.jobs?.job ?? [];
  return (
    <div>
      <h2>My OPUS Jobs</h2>
      {err && <p className="error">{err}</p>}
      <table>
        <thead><tr><th>ID</th><th>Phase</th><th>Created</th></tr></thead>
        <tbody>
          {items.map((j, i) => (
            <tr key={i}>
              <td>{j["uws:jobId"]}</td>
              <td>{j["uws:phase"]}</td>
              <td>{j["uws:quote"] ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
