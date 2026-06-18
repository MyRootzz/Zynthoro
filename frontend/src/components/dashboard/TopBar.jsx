import { useState } from "react";
import { Bell, ChevronDown, LogOut, User } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";

function greeting() {
  const h = new Date().getHours();
  if (h < 5) return "Good night";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function TopBar({ title }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [notifications] = useState(0);
  const initials = (
    (user?.first_name?.[0] || user?.email?.[0] || "?") + (user?.last_name?.[0] || "")
  ).toUpperCase();

  return (
    <header className="h-[72px] bg-white border-b border-[#eee] flex items-center justify-between px-6 sm:px-8 sticky top-0 z-20">
      <div>
        {title ? (
          <h1 className="text-[20px] font-semibold tracking-tight text-black">{title}</h1>
        ) : (
          <h1 className="text-[20px] font-semibold tracking-tight text-black" data-testid="greeting">
            {greeting()}, {user?.first_name || "there"}
          </h1>
        )}
      </div>
      <div className="flex items-center gap-3">
        {user?.subscription_plan && (
          <span
            className="text-[11.5px] font-semibold tracking-wide uppercase px-2.5 py-1 rounded-full"
            style={{ background: "#EAF0FF", color: "#1A4FFF" }}
            data-testid="plan-badge"
          >
            {user.subscription_plan}
          </span>
        )}
        <button className="relative p-2 rounded-md hover:bg-[#F4F6FB]" aria-label="Notifications" data-testid="notifications">
          <Bell size={18} />
          {notifications > 0 && (
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full" style={{ background: "#1A4FFF" }} />
          )}
        </button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-[#F4F6FB]" data-testid="profile-menu">
              <span
                className="w-8 h-8 rounded-full inline-flex items-center justify-center text-white text-[12px] font-semibold"
                style={{ background: "#1A4FFF" }}
              >
                {initials}
              </span>
              <ChevronDown size={14} className="text-[#666]" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="text-[13px] font-semibold">{user?.first_name} {user?.last_name}</div>
              <div className="text-[11px] text-[#666] font-normal">{user?.email}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/dashboard/settings")}>
              <User size={14} className="mr-2" /> Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
              data-testid="logout"
            >
              <LogOut size={14} className="mr-2" /> Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
