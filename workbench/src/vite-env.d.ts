/// <reference types="vite/client" />

interface Window {
  __VEYRA_SESSION__?: import("./types").SessionPayload;
}
