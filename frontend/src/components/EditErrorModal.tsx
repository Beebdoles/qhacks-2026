"use client";

interface EditErrorModalProps {
  message: string;
  onClose: () => void;
}

export default function EditErrorModal({ message, onClose }: EditErrorModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
      <div className="bg-surface-800 border border-border rounded-xl p-6 max-w-sm w-full mx-4 shadow-xl">
        {/* Warning icon */}
        <div className="flex justify-center mb-4">
          <div className="w-12 h-12 rounded-full bg-amber-500/15 flex items-center justify-center">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-amber-400">
              <path
                d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
        </div>

        <h3 className="text-lg font-semibold text-text-primary text-center mb-2">
          Couldn&apos;t understand command
        </h3>
        <p className="text-sm text-text-secondary text-center mb-6">
          {message}
        </p>

        <button
          onClick={onClose}
          className="w-full py-2.5 px-4 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-lg transition-all duration-150 cursor-pointer"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
