import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "inVision U — приёмная кампания",
    short_name: "inVision U",
    description: "Портал приёмной кампании inVision U",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#8BC525",
    icons: [
      {
        src: "/assets/icons/logo.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/assets/icons/logo.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
