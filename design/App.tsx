import React from "react";
import ReactDOM from "react-dom";
import { DesignCanvas, DCSection, DCArtboard } from "./design-canvas";
import { useTweaks, TweaksPanel, TweakSection, TweakColor, TweakRadio } from "./tweaks-panel";
import { Foundations } from "./components/Foundations";
import { Login } from "./components/Login";
import { ChatA } from "./components/ChatA";
import { ChatB } from "./components/ChatB";
import { ChatEmpty, ChatStreaming, ChatCiteHover } from "./components/ChatStates";
import { AdminDocs } from "./components/AdminDocs";
import { AdminAudit } from "./components/AdminAudit";
import { AdminStats } from "./components/AdminStats";
import { AdminFeedback } from "./components/AdminFeedback";

const TWEAK_DEFAULTS = {
  accent: "#3b6cf2",
  density: "regular",
  showCanvasGrid: true,
};

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  React.useEffect(() => {
    document.documentElement.style.setProperty('--blue', t.accent);
    const hex = t.accent.replace('#','');
    const r = parseInt(hex.slice(0,2),16);
    const g = parseInt(hex.slice(2,4),16);
    const b = parseInt(hex.slice(4,6),16);
    document.documentElement.style.setProperty('--blue-soft', `rgba(${r},${g},${b},0.10)`);
    document.documentElement.style.setProperty('--blue-tint', `rgba(${r},${g},${b},0.05)`);
  }, [t.accent]);

  React.useEffect(() => {
    document.documentElement.style.setProperty('--pa-density-scale',
      t.density === 'compact' ? '0.94' : t.density === 'comfy' ? '1.06' : '1');
  }, [t.density]);

  return (
    <>
      <DesignCanvas>
        <DCSection id="brand" title="01 · Foundations" subtitle="Tone, palette and primitives the rest of the work is built from.">
          <DCArtboard id="found" label="Brand foundations" width={1280} height={720}>
            <Foundations/>
          </DCArtboard>
        </DCSection>
        <DCSection id="auth" title="02 · Sign in" subtitle="A single quiet entry point. SSO-first, password second.">
          <DCArtboard id="login" label="Login · split" width={1280} height={780}>
            <Login/>
          </DCArtboard>
        </DCSection>
        <DCSection id="chat" title="03 · Chat — pilot user" subtitle="Two takes on the same conversation, side-by-side.">
          <DCArtboard id="chat-a" label="A · Centered, citation drawer" width={1280} height={820}>
            <ChatA/>
          </DCArtboard>
          <DCArtboard id="chat-b" label="B · Three-pane workbench" width={1440} height={820}>
            <ChatB/>
          </DCArtboard>
        </DCSection>
        <DCSection id="chat-states" title="04 · Chat — micro-interactions" subtitle="Empty state with corpus-aware prompts, streaming pipeline view, and the inline citation hover preview.">
          <DCArtboard id="empty" label="Empty state · suggested prompts" width={1280} height={820}>
            <ChatEmpty/>
          </DCArtboard>
          <DCArtboard id="stream" label="Streaming · pipeline visible" width={1280} height={820}>
            <ChatStreaming/>
          </DCArtboard>
          <DCArtboard id="cite" label="Citation hover · PDF peek" width={1280} height={780}>
            <ChatCiteHover/>
          </DCArtboard>
        </DCSection>
        <DCSection id="admin" title="05 · Admin" subtitle="Reframed as a calm document store + activity log + briefing — not a tile dashboard.">
          <DCArtboard id="admin-docs" label="Documents · upload + indexing" width={1440} height={820}>
            <AdminDocs/>
          </DCArtboard>
          <DCArtboard id="admin-audit" label="Activity · stream view" width={1440} height={820}>
            <AdminAudit/>
          </DCArtboard>
          <DCArtboard id="admin-stats" label="Overview · daily briefing" width={1280} height={820}>
            <AdminStats/>
          </DCArtboard>
          <DCArtboard id="admin-feedback" label="Feedback · trace review" width={1440} height={820}>
            <AdminFeedback/>
          </DCArtboard>
        </DCSection>
      </DesignCanvas>

      <TweaksPanel>
        <TweakSection label="Accent"/>
        <TweakColor label="Action color" value={t.accent}
          options={['#3b6cf2', '#1f8a5b', '#7a5ae0', '#c66338', '#0a0a0a']}
          onChange={(v: string) => setTweak('accent', v)} />
        <TweakSection label="Density"/>
        <TweakRadio label="Spacing" value={t.density}
          options={['compact', 'regular', 'comfy']}
          onChange={(v: string) => setTweak('density', v)} />
      </TweaksPanel>
    </>
  );
}

export default App;

const root = document.getElementById('root');
if (root) {
  ReactDOM.createRoot(root).render(<App/>);
}
