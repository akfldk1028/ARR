import TopBar from "@/components/TopBar";
import { Outlet } from "react-router-dom";
import HistorySidebar from "../HistorySidebar";
import Halo from "../Halo";

const Layout = () => {
	return (
		<div className="h-full flex flex-col relative overflow-hidden">
			<TopBar />
			<div className="flex-1 h-full min-h-0 overflow-hidden relative">
				<Outlet />
				<HistorySidebar />
				<Halo />
			</div>
		</div>
	);
};

export default Layout;
