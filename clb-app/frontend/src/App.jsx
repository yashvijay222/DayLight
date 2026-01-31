import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import Analysis from "./pages/Analysis";
import Home from "./pages/Home";
import Onboarding from "./pages/Onboarding";

const App = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/onboarding" />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/analysis" element={<Analysis />} />
      <Route path="/dashboard" element={<Home />} />
    </Routes>
  );
};

export default App;
