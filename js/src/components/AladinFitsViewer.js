import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../apiClients";

export default function AladinFitsViewer({
  fitsPath,
  height = 560,
  colormap = "magma",
  stretch = "sqrt",
  cuts = [0, 8],
  baseSurvey = "https://alasky.cds.unistra.fr/DSS/DSS2Merged/",
}) {
  const divId = useMemo(() => `aladin-fits-${Math.random().toString(16).slice(2)}`, []);
  const aladinRef = useRef(null);
  const lastSurveyRef = useRef(null);
  const objectUrlRef = useRef(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    setErr("");

    if (!fitsPath) return;

    const A = window.A;
    if (!A) {
      setErr("Aladin Lite is not loaded (window.A missing).");
      return;
    }

    const initPromise = A.init?.then ? A.init : Promise.resolve();

    async function run() {
      try {
        await initPromise;
        if (cancelled) return;

        const resp = await apiClient.get(fitsPath, { responseType: "blob" });
        if (cancelled) return;

        if (objectUrlRef.current) {
          URL.revokeObjectURL(objectUrlRef.current);
          objectUrlRef.current = null;
        }

        const blobUrl = URL.createObjectURL(resp.data);
        objectUrlRef.current = blobUrl;

        if (!aladinRef.current || lastSurveyRef.current !== baseSurvey) {
          const el = document.getElementById(divId);
          if (el) el.innerHTML = "";

          aladinRef.current = A.aladin(`#${divId}`, {
            survey: baseSurvey,
            fov: 2,
            cooFrame: "icrs",
            showReticle: true,
            showFrame: true,
          });
          lastSurveyRef.current = baseSurvey;
        }

        const aladin = aladinRef.current;

        aladin.displayFITS(blobUrl, (ra, dec, fov, image) => {
          if (cancelled) return;
          try {
            if (Number.isFinite(ra) && Number.isFinite(dec)) aladin.gotoRaDec(ra, dec);
            if (Number.isFinite(fov)) aladin.setFoV(2 * fov);

            if (image?.setColormap) image.setColormap(colormap, { stretch, reversed: false });
            if (image?.setCuts && Array.isArray(cuts) && cuts.length === 2) {
              image.setCuts(cuts[0], cuts[1]);
            }
          } catch (e) {
            console.warn("Aladin FITS styling failed:", e);
          }
        });
      } catch (e) {
        if (!cancelled) setErr(e?.message || String(e));
      }
    }

    run();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [fitsPath, divId, colormap, stretch, cuts, baseSurvey]);

  return (
    <div>
      {err && <div className="alert alert-warning mb-2">FITS viewer: {err}</div>}
      <div
        id={divId}
        style={{
          width: "100%",
          height,
          border: "1px solid #ddd",
          borderRadius: 6,
          overflow: "hidden",
        }}
      />
    </div>
  );
}
