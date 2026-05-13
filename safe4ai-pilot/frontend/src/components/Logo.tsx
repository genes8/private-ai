export default function Logo({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="40" height="40" rx="9" fill="#0b0d10" />
      <path d="M9 9 L31 9 L9 31 Z" fill="#f4f1ea" />
      <rect x="25" y="7" width="9" height="9" rx="2" fill="#3b6cf2" />
    </svg>
  );
}
