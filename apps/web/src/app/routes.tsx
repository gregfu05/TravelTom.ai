import { Navigate, Route, Routes } from "react-router-dom";

import { HomePage } from "../pages/HomePage/HomePage";
import { HowItWorksPage } from "../pages/HowItWorksPage/HowItWorksPage";
import { LoginPage } from "../pages/LoginPage/LoginPage";
import { PlannerPage } from "../pages/PlannerPage/PlannerPage";
import { SignupPage } from "../pages/SignupPage/SignupPage";
import { WhyTravelTomPage } from "../pages/WhyTravelTomPage/WhyTravelTomPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/planner" element={<PlannerPage />} />
      <Route path="/why-traveltom" element={<WhyTravelTomPage />} />
      <Route path="/how-it-works" element={<HowItWorksPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="*" element={<Navigate replace to="/" />} />
    </Routes>
  );
}
