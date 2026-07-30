import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar/Sidebar';
import Navbar from '../components/Navbar/Navbar';

export const StudentLayout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-container">
      <Sidebar isOpen={sidebarOpen} unreadCount={2} />
      
      <div className="main-content-wrapper">
        <Navbar onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} unreadCount={2} />
        
        <main className="page-container">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default StudentLayout;
