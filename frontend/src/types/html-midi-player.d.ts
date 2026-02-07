import "react";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "midi-player": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          src?: string;
          "sound-font"?: string | boolean;
          visualizer?: string;
        },
        HTMLElement
      >;
      "midi-visualizer": React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          src?: string;
          type?: "piano-roll" | "waterfall" | "staff";
        },
        HTMLElement
      >;
    }
  }
}
