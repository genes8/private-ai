import React from "react";

type IconComponent = (props: {
  size?: number;
  stroke?: string;
  strokeWidth?: number;
  fill?: string;
  style?: React.CSSProperties;
}) => React.ReactElement;

const I = (paths: React.ReactElement, opts: Record<string, unknown> = {}): IconComponent => {
  const Comp = ({ size = 14, stroke = "currentColor", strokeWidth = 1.5, fill = "none", style }: {
    size?: number;
    stroke?: string;
    strokeWidth?: number;
    fill?: string;
    style?: React.CSSProperties;
  }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke}
         strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
         style={{ display: "inline-block", verticalAlign: "-2px", ...style }}
         {...opts}>
      {paths}
    </svg>
  );
  Comp.displayName = "IconVariant";
  return Comp;
};

const Icon = {
  Search:    I(<><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></>),
  Send:      I(<><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4 20-7Z"/></>),
  Plus:      I(<><path d="M12 5v14M5 12h14"/></>),
  Sparkle:   I(<><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></>),
  ThumbUp:   I(<><path d="M7 22V11"/><path d="M3 11h4v11H3z"/><path d="M7 11l4-9c1.5 0 3 1 3 3v4h5a3 3 0 0 1 3 3l-1.5 7a3 3 0 0 1-3 2H7"/></>),
  ThumbDown: I(<><path d="M17 2v11"/><path d="M21 13h-4V2h4z"/><path d="M17 13l-4 9c-1.5 0-3-1-3-3v-4H5a3 3 0 0 1-3-3l1.5-7a3 3 0 0 1 3-2H17"/></>),
  Copy:      I(<><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>),
  Doc:       I(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></>),
  DocText:   I(<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h6M8 9h2"/></>),
  Folder:    I(<><path d="M4 4h6l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z"/></>),
  Upload:    I(<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/></>),
  Settings:  I(<><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"/></>),
  Users:     I(<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></>),
  Activity:  I(<><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></>),
  Chart:     I(<><path d="M3 3v18h18"/><path d="M7 14l3-3 3 3 5-5"/></>),
  Lock:      I(<><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>),
  Shield:    I(<><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></>),
  ChevR:     I(<><path d="m9 18 6-6-6-6"/></>),
  ChevD:     I(<><path d="m6 9 6 6 6-6"/></>),
  ChevL:     I(<><path d="m15 18-6-6 6-6"/></>),
  X:         I(<><path d="M18 6 6 18M6 6l12 12"/></>),
  Check:     I(<><path d="M20 6 9 17l-5-5"/></>),
  Dots:      I(<><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></>, { fill: "currentColor", stroke: "none" }),
  Filter:    I(<><path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3Z"/></>),
  Trash:     I(<><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></>),
  Refresh:   I(<><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M3 21v-5h5"/></>),
  Eye:       I(<><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>),
  Download:  I(<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/></>),
  External:  I(<><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14 21 3"/></>),
  Bolt:      I(<><path d="M13 2 3 14h9l-1 8 10-12h-9l1-8Z"/></>),
  Clock:     I(<><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></>),
  Hash:      I(<><path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/></>),
  Brain:     I(<><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/></>),
  Inbox:     I(<><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/></>),
  Stack:     I(<><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 17 9 5 9-5"/><path d="m3 12 9 5 9-5"/></>),
  Spark:     I(<><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/><path d="m4.93 4.93 2.83 2.83M16.24 16.24l2.83 2.83M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></>),
  Mic:       I(<><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3"/></>),
  Paper:     I(<><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/></>),
  At:        I(<><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"/></>),
};

export { Icon };
