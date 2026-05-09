// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
contract AgentTokenLaunchpad {
    address public immutable treasury;
    uint256 public constant FEE_BPS = 100;
    uint256 public launchCount;
    struct Launch { address deployer; string name; string ticker; uint256 reserveWei; uint256 supply; bool graduated; }
    mapping(uint256 => Launch) public launches;
    event TokenLaunched(uint256 indexed id, address indexed deployer, string ticker);
    event Trade(uint256 indexed id, address indexed trader, bool isBuy, uint256 amountIn, uint256 fee, uint256 virtualTokensOut);
    constructor(address _treasury){ treasury=_treasury; }
    function launch(string calldata name, string calldata ticker) external returns(uint256 id){ id=++launchCount; launches[id]=Launch(msg.sender,name,ticker,0,0,false); emit TokenLaunched(id,msg.sender,ticker); }
    function quoteBuy(uint256 id,uint256 amountWei) public view returns(uint256 fee,uint256 out){ Launch storage t=launches[id]; fee=amountWei*FEE_BPS/10000; uint256 net=amountWei-fee; uint256 price=1e14+(t.supply/1000000)*1e10; out=(net*1e18)/price; }
    function buy(uint256 id) external payable { Launch storage t=launches[id]; require(!t.graduated,"graduated"); (uint256 fee,uint256 out)=quoteBuy(id,msg.value); t.reserveWei+=msg.value-fee; t.supply+=out; payable(treasury).transfer(fee); emit Trade(id,msg.sender,true,msg.value,fee,out); if(t.reserveWei>=69 ether){ t.graduated=true; } }
}
