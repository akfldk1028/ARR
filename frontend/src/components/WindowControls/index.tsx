import { Minus, Square, X } from "lucide-react";
import { useRef, useEffect, useState } from "react";
import { getPlatform, safeElectronAPI, isElectron } from "@/utils/electron";
import "./index.css";

export default function WindowControls() {
	const controlsRef = useRef<HTMLDivElement>(null);
	const [platform, setPlatform] = useState<string>("");

	useEffect(() => {
		const p = getPlatform();
		setPlatform(p);

		if (p === "darwin") {
			if (controlsRef.current) {
				controlsRef.current.style.display = "none";
			}
		}
	}, []);

	// Don't show window controls in web browser or on macOS
	if (platform === "darwin" || platform === "web") {
		return null;
	}

	return (
		<div
			className="window-controls h-full flex items-center"
			id="window-controls"
			ref={controlsRef}
			style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
		>
			<div
				className="control-btn h-full flex-1"
				onClick={() => safeElectronAPI((api) => api.minimizeWindow())}
			>
				<Minus className="w-4 h-4" />
			</div>
			<div
				className="control-btn h-full flex-1"
				onClick={() => safeElectronAPI((api) => api.toggleMaximizeWindow())}
			>
				<Square className="w-4 h-4" />
			</div>
			<div
				className="control-btn h-full flex-1"
				onClick={(e) => {
					e.stopPropagation();
					e.preventDefault();
					// Trigger window close - this will go through the before-close handler
					// which checks if tasks are running and shows confirmation if needed
					safeElectronAPI((api) => api.closeWindow(false));
				}}
				onMouseDown={(e) => {
					e.stopPropagation();
				}}
			>
				<X className="w-4 h-4" />
			</div>
		</div>
	);
}

