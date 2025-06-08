import React, { useEffect, useState, useCallback, useRef } from 'react';
import mermaid from 'mermaid'; // Should be existing
import { Loader2, X, AlertTriangle } from 'lucide-react'; // Ensure all are listed

// Initialize Mermaid.js once when this module is loaded.
// This configuration applies to all Mermaid diagrams rendered by this instance.
try {
  mermaid.initialize({
    startOnLoad: false, // We will call render manually
    theme: 'dark',      // Options: 'dark', 'neutral', 'forest', 'default'
    // Set a font family that matches your app's theme for consistency in diagrams
    fontFamily: '"Inter", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"',
    // securityLevel: 'strict', // 'strict', 'sandbox', 'loose'. Default is 'strict'.
                              // 'strict' prevents script execution. Good for LLM generated content.
  });
} catch (e) {
  console.error("Mermaid.js initialization error:", e);
  // This error typically means Mermaid couldn't initialize properly in the environment.
  // The modal might still work but Mermaid diagrams won't render.
}

// Define ChatMessage interface (basic version)
interface ChatMessage {
  id: string;
  type: string;
  content: string | any;
}

// Define Props for the MindMapModal
interface MindMapModalProps {
  isOpen: boolean;
  onClose: () => void;
  chatHistory: ChatMessage[]; // Will be used to pass chat history
  apiUrlBase: string;      // Will be used for API calls
}

// MindMapModal component
export const MindMapModal: React.FC<MindMapModalProps> = ({
  isOpen,
  onClose,
  chatHistory, // Now used
  apiUrlBase,  // Now used
}) => {
  const mermaidDivRef = useRef<HTMLDivElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawMermaid, setRawMermaid] = useState<string>("");

  if (!isOpen) {
    return null; // Don't render anything if the modal is not open
  }

  useEffect(() => {
    if (isOpen && chatHistory.length > 0) {
      setIsLoading(true);
      setError(null);
      setRawMermaid("");

      const historyPayload = chatHistory.map(msg => ({
        type: msg.type,
        content: typeof msg.content === 'string' ? msg.content.substring(0, 300) : JSON.stringify(msg.content).substring(0, 300)
      }));

      fetch(`${apiUrlBase}/mindmap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: historyPayload }),
      })
        .then(res => {
          if (!res.ok) {
            return res.text().then(text => {
              let detail = text;
              try {
                  const errJson = JSON.parse(text);
                  detail = errJson.detail || text;
              } catch (e) { /* ignore */ }
              throw new Error(`Server error (status ${res.status}): ${detail}`);
            });
          }
          return res.json();
        })
        .then(data => {
          if (data.mermaid_string) {
            setRawMermaid(data.mermaid_string);
          } else {
            setRawMermaid("");
            throw new Error("Received no mermaid_string or empty data in response.");
          }
        })
        .catch(err => {
          console.error("Mind map fetch error:", err);
          setError(err.message || "Could not load mind map data.");
          setRawMermaid("");
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else if (!isOpen) {
      // Optional: Clear state when modal is closed
      // setRawMermaid("");
      // setError(null);
    }
  }, [isOpen, chatHistory, apiUrlBase]);

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-85 flex items-center justify-center p-2 sm:p-4 z-[100]"
      aria-modal="true"
      role="dialog"
    >
      <div className="bg-neutral-800 p-3 sm:p-5 rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col text-neutral-100">
        {/* Modal Header */}
        <div className="flex justify-between items-center mb-3 sm:mb-4">
          <h2 className="text-lg sm:text-xl font-semibold">Conversation Mind Map</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-100 p-1 rounded-full transition-colors"
            aria-label="Close mind map"
          >
            <X size={22} /> {/* Use X icon */}
          </button>
        </div>

        {/* Modal Body - Placeholder for dynamic content */}
        <div className="flex-grow overflow-auto p-1 sm:p-2 bg-neutral-900/70 rounded min-h-[250px] sm:min-h-[350px] border border-neutral-700">
          {/* Content will go here: Loading indicator, error message, or Mermaid diagram */}
          {/* For now, a simple placeholder: */}
          <div className="mermaid-placeholder w-full h-full flex justify-center items-center p-2 min-h-[200px]">
            <p className="text-neutral-500 text-sm">Mind map content will appear here.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
