import { lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Layout from "@/components/Layout";
// Lazy load page components
const Login = lazy(() => import("@/pages/Login"));
const Signup = lazy(() => import("@/pages/SignUp"));
const Home = lazy(() => import("@/pages/Home"));
const History = lazy(() => import("@/pages/History"));
const Setting = lazy(() => import("@/pages/Setting"));
const NotFound = lazy(() => import("@/pages/NotFound"));
const SettingGeneral = lazy(() => import("@/pages/Setting/General"));
const SettingPrivacy = lazy(() => import("@/pages/Setting/Privacy"));
const SettingModels = lazy(() => import("@/pages/Setting/Models"));
const SettingAPI = lazy(() => import("@/pages/Setting/API"));
const SettingMCP = lazy(() => import("@/pages/Setting/MCP"));
const MCPMarket = lazy(() => import("@/pages/Setting/MCPMarket"));
const LawChat = lazy(() => import("@/law/LawChat"));
const LandMap = lazy(() => import("@/land/LandMap"));
const DesignPage = lazy(() => import("@/design/DesignPage"));

// Main route configuration — no auth guard, all public
const AppRoutes = () => (
	<Routes>
		<Route path="/login" element={<Login />} />
		<Route path="/signup" element={<Signup />} />
		<Route path="/law" element={<LawChat />} />
		<Route path="/land" element={<LandMap />} />
		<Route path="/design" element={<DesignPage />} />
		<Route element={<Layout />}>
			<Route path="/" element={<Navigate to="/law" replace />} />
			<Route path="/history" element={<History />} />
			<Route path="/setting" element={<Setting />}>
				<Route index element={<Navigate to="general" replace />} />
				<Route path="general" element={<SettingGeneral />} />
				<Route path="privacy" element={<SettingPrivacy />} />
				<Route path="models" element={<SettingModels />} />
				<Route path="api" element={<SettingAPI />} />
				<Route path="mcp" element={<SettingMCP />} />
				<Route path="mcp_market" element={<MCPMarket />} />
			</Route>
		</Route>
		<Route path="*" element={<NotFound />} />
	</Routes>
);

export default AppRoutes;
