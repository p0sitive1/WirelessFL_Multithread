function [x] = fmin(A,B,c,x0,Aeq,lb,ub)

    fun = @(x)(x(1)*A(1)+x(2)*A(2)+x(3)*A(3)+x(4)*A(4)+x(5)*A(5)+x(6)*A(6)+x(7)*A(7)+x(8)*A(8)+x(9)*A(9)+x(10)*A(10)+x(11)*A(11)+x(12)*A(12)+x(13)*A(13)+x(14)*A(14)+x(15)*A(15)+x(16)*A(16)+x(17)*A(17)+x(18)*A(18)+x(19)*A(19)+x(20)*A(20)+x(21)*A(21)+x(22)*A(22)+x(23)*A(23)+x(24)*A(24)+x(25)*A(25)+x(26)*A(26)+x(27)*A(27)+x(28)*A(28)+x(29)*A(29)+x(30)*A(30)+x(31)*A(31)+x(32)*A(32)+x(33)*A(33)+x(34)*A(34)+x(35)*A(35)+x(36)*A(36)+x(37)*A(37)+x(38)*A(38)+x(39)*A(39)+x(40)*A(40))*((B(1)/x(1)+B(2)/x(2)+B(3)/x(3)+B(4)/x(4)+B(5)/x(5)+B(6)/x(6)+B(7)/x(7)+B(8)/x(8)+B(9)/x(9)+B(10)/x(10)+B(11)/x(11)+B(12)/x(12)+B(13)/x(13)+B(14)/x(14)+B(15)/x(15)+B(16)/x(16)+B(17)/x(17)+B(18)/x(18)+B(19)/x(19)+B(20)/x(20)+B(21)/x(21)+B(22)/x(22)+B(23)/x(23)+B(24)/x(24)+B(25)/x(25)+B(26)/x(26)+B(27)/x(27)+B(28)/x(28)+B(29)/x(29)+B(30)/x(30)+B(31)/x(31)+B(32)/x(32)+B(33)/x(33)+B(34)/x(34)+B(35)/x(35)+B(36)/x(36)+B(37)/x(37)+B(38)/x(38)+B(39)/x(39)+B(40)/x(40))+c(1));
    beq=1;
    MyValue=10e5;
    options = optimoptions('fmincon','Algorithm','sqp', 'MaxFunctionEvaluations',MyValue);
    [x,fmin] = fmincon(fun, x0,[],[],Aeq,beq,lb,ub,[],options);

