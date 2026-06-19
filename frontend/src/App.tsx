import AppRoutes from "@/routers/index";
import { Toaster } from "sonner";

function App() {
	return (
		<>
			<AppRoutes />
			<Toaster style={{ zIndex: "999999 !important", position: "fixed" }} />
		</>
	);
}

export default App;
