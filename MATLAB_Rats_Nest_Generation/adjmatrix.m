function amatrix = adjmatrix(forces,pos)

nrow = size(forces,1);
temp = zeros(nrow,3);
all = [forces,temp];

for a=1:nrow
    for c=7:9
        b=1;
        while forces(a,2)~=pos(b,1)
        b=b+1;
        end
        all(a,c)=pos(b,c-5);
    end
end

for a=1:nrow    
    for c=10:12
        b=1;
        while forces(a,3)~=pos(b,1)
        b=b+1;
        end
        all(a,c)=pos(b,c-8);
    end
end

amatrix=zeros(size(pos,1),size(pos,1));

for a=1:nrow
    nf=sqrt(all(a,4)^2+all(a,5)^2+all(a,6)^2);
    amatrix(all(a,2),all(a,3))=nf; %matrix index corresponds to atom id
    amatrix(all(a,3),all(a,2))=nf;
end



return;